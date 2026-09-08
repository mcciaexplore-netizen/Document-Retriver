"""Start the local document app without requiring PowerShell script execution."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from urllib.request import ProxyHandler, build_opener

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
SERVICE = "MCCIA Enterprise Document Search"
HTTP = build_opener(ProxyHandler({}))


def healthy(url: str) -> bool:
    try:
        with HTTP.open(url + "/api/health", timeout=2) as response:
            data = json.load(response)
        return data.get("status") == "ok" and data.get("service") == SERVICE
    except (OSError, ValueError):
        return False


def occupied(port: int) -> bool:
    with socket.socket() as connection:
        connection.settimeout(1)
        return connection.connect_ex(("127.0.0.1", port)) == 0


def main() -> int:
    settings = {**os.environ, **{k: v for k, v in dotenv_values(ROOT / ".env").items() if v is not None}}
    backend_port = int(settings.get("BACKEND_PORT", "8000"))
    frontend_port = int(settings.get("FRONTEND_PORT", "3000"))
    if not all(1 <= port <= 65535 for port in (backend_port, frontend_port)):
        raise RuntimeError("Service ports must be between 1 and 65535.")
    if backend_port == frontend_port:
        raise RuntimeError("FRONTEND_PORT and BACKEND_PORT must be different.")
    backend_url = f"http://127.0.0.1:{backend_port}"
    frontend_url = f"http://127.0.0.1:{frontend_port}"
    settings["BACKEND_URL"] = backend_url
    settings["NEXT_TELEMETRY_DISABLED"] = "1"
    settings.setdefault("CORS_ORIGINS", f"{frontend_url},http://localhost:{frontend_port}")
    node = shutil.which("node")
    next_cli = ROOT / "node_modules/next/dist/bin/next"
    if not node or not next_cli.is_file():
        raise RuntimeError("Install Node.js and run npm ci in the project root first.")
    children: list[subprocess.Popen] = []

    def start(command, directory):
        child = subprocess.Popen(command, cwd=directory, env=settings)
        children.append(child)
        return child

    def wait_ready(url, child):
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if child.poll() is not None:
                raise RuntimeError(f"Service exited with code {child.returncode}; see its error above.")
            if healthy(url):
                return
            time.sleep(0.5)
        raise RuntimeError(f"Service did not become healthy at {url} within 90 seconds.")

    try:
        if not healthy(backend_url):
            if occupied(backend_port):
                raise RuntimeError(f"Port {backend_port} belongs to another service. Change BACKEND_PORT in .env.")
            subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=settings, check=True)
            child = start([sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(backend_port)], ROOT)
            wait_ready(backend_url, child)
        print(f"Backend ready: {backend_url}", flush=True)
        if not healthy(frontend_url):
            if occupied(frontend_port):
                raise RuntimeError(f"Port {frontend_port} is busy but its document API is unavailable. Stop the old frontend and run this launcher again.")
            child = start([node, str(next_cli), "dev", "--hostname", "127.0.0.1", "--port", str(frontend_port)], ROOT)
            wait_ready(frontend_url, child)
        print(f"App ready: {frontend_url} (frontend API connection verified). Press Ctrl+C to stop services started here.", flush=True)
        while children:
            if any(child.poll() is not None for child in children):
                raise RuntimeError("A service stopped unexpectedly; see its error above.")
            time.sleep(1)
        return 0
    finally:
        for child in reversed(children):
            if child.poll() is None:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    child.terminate()
                child.wait(timeout=10)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Services stopped.")
    except Exception as error:
        print(f"Startup failed: {error}", file=sys.stderr)
        raise SystemExit(1)
