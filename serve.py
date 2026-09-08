"""Run the production frontend and backend behind one public HTTP port."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
from urllib.request import ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parent


def service_environment(source):
    env = dict(source)
    port = int(env.get("PORT", "10000"))
    api_port = int(env.get("INTERNAL_API_PORT", "8000"))
    if not all(1 <= value <= 65535 for value in (port, api_port)) or port == api_port:
        raise ValueError("PORT and INTERNAL_API_PORT must be different valid ports.")
    origins = [value.strip().rstrip("/") for value in env.get("CORS_ORIGINS", "").split(",") if value.strip()]
    external_url = env.get("RENDER_EXTERNAL_URL", "").rstrip("/")
    if external_url and external_url not in origins:
        origins.append(external_url)
    if origins:
        env["CORS_ORIGINS"] = ",".join(origins)
    env.update(PORT=str(port), HOSTNAME="0.0.0.0", NODE_ENV="production", NEXT_TELEMETRY_DISABLED="1")
    return env, port, api_port


def main():
    env, port, api_port = service_environment(os.environ)
    frontend = Path(env.get("FRONTEND_DIR", str(ROOT / "frontend"))).resolve()
    node = shutil.which("node")
    if not node or not (frontend / "server.js").is_file():
        raise RuntimeError("Build Dockerfile.fullstack before starting the production service.")
    Path(env.get("STORAGE_PATH", str(ROOT / "storage"))).mkdir(parents=True, exist_ok=True)
    children = []
    stopping = False

    def stop(_signum, _frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    http = build_opener(ProxyHandler({}))

    def start(command, cwd):
        child = subprocess.Popen(command, cwd=cwd, env=env)
        children.append(child)
        return child

    def ready(target_port):
        deadline = time.monotonic() + 90
        while not stopping and time.monotonic() < deadline:
            if any(child.poll() is not None for child in children):
                raise RuntimeError("A service exited during startup; check the preceding logs.")
            try:
                with http.open(f"http://127.0.0.1:{target_port}/api/health", timeout=2) as response:
                    health = json.load(response)
                if health.get("status") == "ok" and health.get("service") == "MCCIA Enterprise Document Search":
                    return
            except (OSError, ValueError):
                pass
            time.sleep(0.25)
        if not stopping:
            raise RuntimeError(f"Service on port {target_port} did not become healthy.")

    try:
        migration = start([sys.executable, "-m", "alembic", "upgrade", "head"], ROOT)
        while migration.poll() is None and not stopping:
            time.sleep(0.1)
        if stopping:
            return 0
        if migration.returncode:
            raise RuntimeError("Database migrations failed.")
        children.remove(migration)
        start([sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(api_port)], ROOT)
        ready(api_port)
        if stopping:
            return 0
        start([node, "server.js"], frontend)
        ready(port)
        if not stopping:
            print(f"Document Retriever ready on port {port}: frontend and backend connected.", flush=True)
        while not stopping:
            if any(child.poll() is not None for child in children):
                raise RuntimeError("A service stopped unexpectedly; restarting the container is required.")
            time.sleep(0.5)
        return 0
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=5)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Startup failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
