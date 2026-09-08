import asyncio
import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.core.config import settings
from app.core.security import decode_user
from app.database.session import SessionLocal
from app.api.routes import router
from app.scheduler.jobs import scheduled_check
from app.websocket.manager import manager


@asynccontextmanager
async def lifespan(app):
    scheduler = AsyncIOScheduler()
    if settings.scheduler_enabled:
        scheduler.add_job(scheduled_check, 'interval', minutes=1, max_instances=1, coalesce=True)
        scheduler.start()
    yield
    if scheduler.running:
        scheduler.shutdown(wait=False)


app = FastAPI(title='Voicelytics Factory Operations', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins.split(','), allow_credentials=False,
                   allow_methods=['GET', 'POST', 'PUT', 'DELETE'], allow_headers=['Authorization', 'Content-Type', 'X-API-Key'])
app.include_router(router)
requests = defaultdict(deque)


@app.middleware('http')
async def safeguards(request: Request, call_next):
    now = time.monotonic()
    login = request.url.path == '/api/auth/login'
    identity = (request.client.host, 'login' if login else 'api')
    bucket = requests[identity]
    while bucket and now - bucket[0] >= 60:
        bucket.popleft()
    if len(bucket) >= (10 if login else 600):
        return JSONResponse({'detail': 'Too many requests. Try again in one minute.'}, status_code=429, headers={'Retry-After': '60'})
    bucket.append(now)
    if len(requests) > 10000:
        for key in list(requests):
            if requests[key] and now - requests[key][-1] > 60:
                requests.pop(key, None)
    length = request.headers.get('content-length')
    if length and (not length.isdigit() or int(length) > 27 * 1024 * 1024):
        return JSONResponse({'detail': 'Request is too large'}, status_code=413)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Cache-Control'] = 'no-store'
    return response


@app.exception_handler(IntegrityError)
async def integrity_error(request, exc):
    return JSONResponse({'detail': 'Duplicate record or a related record prevents this change.'}, status_code=409)


@app.exception_handler(Exception)
async def server_error(request, exc):
    logging.exception('Request failed: %s', request.url.path, exc_info=exc)
    return JSONResponse({'detail': 'The server could not complete this request. Please retry.'}, status_code=500)


@app.get('/health')
def health():
    with SessionLocal() as db:
        db.execute(text('SELECT 1'))
    return {'status': 'ok'}


@app.websocket('/ws')
async def websocket_endpoint(websocket: WebSocket):
    try:
        with SessionLocal() as db:
            user = decode_user(websocket.query_params.get('ticket', ''), db, 'websocket')
        await manager.connect(websocket, user.id)
        connected = time.monotonic()
        while True:
            message = await asyncio.wait_for(websocket.receive_text(), timeout=75)
            with SessionLocal() as db:
                from app.models.entities import User
                active = db.get(User, user.id)
                if not active or not active.is_active or time.monotonic() - connected > 1800:
                    await websocket.close(code=1008); break
            if message == 'ping':
                await websocket.send_json({'type': 'pong'})
    except (HTTPException, WebSocketDisconnect, asyncio.TimeoutError):
        try:
            await websocket.close(code=1008)
        except RuntimeError:
            pass
    finally:
        manager.disconnect(websocket)
