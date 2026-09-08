import csv
import hashlib
import io
import json
import logging
import os
import re
import time
import uuid
from collections import Counter, defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated

import fitz
from fastapi import BackgroundTasks, Depends, FastAPI, File as UploadFileField, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from openpyxl.utils import column_index_from_string

from . import config
from .database import SessionLocal, engine, get_db, init_db
from .indexing import process_file, storage_file
from .models import AuditLog, File, LoginSession, Membership, PDFPage, PresentationSlide, ProcessingJob, SearchHistory, SearchRecord, User, Workspace, utcnow
from .schemas import LoginInput, MembershipInput, PasswordInput, RegisterInput, SearchInput, UserInput, WorkspaceInput
from .search_engine import citation_text, iso, location_for, result_json, run_search
from .security import check_workspace, create_session, current_user, hash_password, require_admin, require_editor, token_hash, verify_password, visible_workspace_ids

logger = logging.getLogger(__name__)
login_attempts = defaultdict(deque)
registration_attempts = defaultdict(deque)


@asynccontextmanager
async def lifespan(_app):
    config.STORAGE_PATH.mkdir(parents=True, exist_ok=True)
    init_db()
    with SessionLocal() as db:
        # A stopped worker never leaves a document looking as if it is still running.
        for job in db.query(ProcessingJob).filter(ProcessingJob.status.in_(["queued", "processing"])):
            job.status, job.error, job.completed_at = "failed", "Processing was interrupted by a server restart. Re-index this file to retry.", utcnow()
            file = db.get(File, job.file_id)
            if file:
                file.processing_status, file.error = "failed", job.error
        db.query(LoginSession).filter(LoginSession.expires_at < utcnow()).delete(synchronize_session=False)
        db.commit()
    from .seed import bootstrap
    bootstrap()
    yield


app = FastAPI(title="MCCIA Enterprise Document Search", description="Private deterministic search, exact citations and audit trails.", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_credentials=True, allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Content-Type"])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    origin = request.headers.get("origin")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and origin and origin not in config.CORS_ORIGINS:
        return JSONResponse({"detail": "This request origin is not allowed."}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(SQLAlchemyError)
async def database_error(_request, exc):
    logger.error("Database operation failed: %s", type(exc).__name__)
    return JSONResponse({"detail": "The database is temporarily unavailable. Please try again."}, status_code=503)


def user_json(user):
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role}


def audit(db, user, action, workspace_id=None, file=None, query="", location="", status="success", details=None):
    db.add(AuditLog(user_id=user.id if user else None, user_name=user.name if user else "System", workspace_id=workspace_id, action=action, query=query, file_id=file.id if file else None, file_name=file.filename if file else "", location=location, status=status, details_json=details or {}))


def file_json(db, file):
    job = db.query(ProcessingJob).filter_by(file_id=file.id).order_by(ProcessingJob.id.desc()).first()
    return {"id": file.id, "workspace_id": file.workspace_id, "filename": file.filename, "name": file.filename, "file_type": file.file_type, "type": file.file_type, "file_size": file.file_size, "size": file.file_size, "source_type": file.source_type, "source": file.source_type, "category": file.category, "processing_status": file.processing_status, "status": file.processing_status, "indexed_records": file.indexed_records, "uploaded_at": iso(file.uploaded_at), "upload_date": iso(file.uploaded_at), "last_modified": iso(file.last_modified), "error": file.error, "job": {"id": job.id, "status": job.status, "progress": job.progress, "error": job.error} if job else None}


def get_file(db, user, file_id):
    file = db.get(File, file_id)
    if not file:
        raise HTTPException(404, "File not found. It may have been deleted.")
    check_workspace(db, user, file.workspace_id)
    return file


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "service": "MCCIA Enterprise Document Search", "database": engine.dialect.name}


@app.post("/api/auth/login")
def login(body: LoginInput, request: Request, response: Response, db: Session = Depends(get_db)):
    key = request.client.host if request.client else "local"
    attempts = login_attempts[key]
    now = time.monotonic()
    while attempts and attempts[0] < now - 60:
        attempts.popleft()
    if len(attempts) >= 15:
        raise HTTPException(429, "Too many sign-in attempts. Please wait one minute.")
    user = db.query(User).filter(User.email == body.email.strip().lower()).first()
    if not user or not verify_password(body.password, user.password_hash):
        attempts.append(now)
        raise HTTPException(401, "The email or password is incorrect.")
    attempts.clear()
    previous = request.cookies.get("mccia_session")
    if previous:
        db.query(LoginSession).filter_by(token_hash=token_hash(previous)).delete(synchronize_session=False)
    token = create_session(db, user)
    audit(db, user, "login")
    db.commit()
    response.set_cookie("mccia_session", token, httponly=True, secure=config.COOKIE_SECURE, samesite="lax", max_age=config.SESSION_HOURS * 3600, path="/")
    return {"user": user_json(user)}


@app.get("/api/auth/options")
def auth_options(db: Session = Depends(get_db)):
    accounts = []
    if config.DEMO_SEED:
        # Only advertise public demo defaults that still work. Never expose
        # environment credentials or passwords chosen by an administrator.
        for email, password, role in (
            ("admin@mccia.org", "Mccia@2026!", "Admin"),
            ("manager@mccia.org", "Manager@2026!", "Manager"),
            ("viewer@mccia.org", "Viewer@2026!", "Viewer"),
        ):
            user = db.query(User).filter_by(email=email, role=role).first()
            if user and verify_password(password, user.password_hash):
                accounts.append({"email": email, "password": password, "role": role})
    return {"account_creation": "self_service" if config.ALLOW_REGISTRATION else "admin_managed", "allow_registration": config.ALLOW_REGISTRATION, "demo_accounts": accounts}


@app.post("/api/auth/register", status_code=201)
def register(body: RegisterInput, request: Request, response: Response, db: Session = Depends(get_db)):
    if not config.ALLOW_REGISTRATION:
        raise HTTPException(403, "Account creation is managed by your administrator.")
    key = request.client.host if request.client else "local"
    attempts = registration_attempts[key]
    now = time.monotonic()
    while attempts and attempts[0] < now - 60:
        attempts.popleft()
    if len(attempts) >= 10:
        raise HTTPException(429, "Too many account creation attempts. Please wait one minute.")
    attempts.append(now)
    if db.query(User).filter_by(email=body.email).first():
        raise HTTPException(409, "An account with this email already exists. Sign in instead.")
    try:
        user = User(name=body.name, email=body.email, password_hash=hash_password(body.password), role="Manager")
        db.add(user)
        db.flush()
        workspace = Workspace(name=f"{body.name[:108]}'s workspace", description="Your personal document workspace.", color="teal")
        db.add(workspace)
        db.flush()
        db.add(Membership(workspace_id=workspace.id, user_id=user.id))
        previous = request.cookies.get("mccia_session")
        if previous:
            db.query(LoginSession).filter_by(token_hash=token_hash(previous)).delete(synchronize_session=False)
        token = create_session(db, user)
        audit(db, user, "register", workspace.id)
        audit(db, user, "workspace_created", workspace.id, details={"name": workspace.name})
        db.commit()
    except IntegrityError:
        db.rollback()
        if db.query(User).filter_by(email=body.email).first():
            raise HTTPException(409, "An account with this email already exists. Sign in instead.")
        raise
    response.set_cookie("mccia_session", token, httponly=True, secure=config.COOKIE_SECURE, samesite="lax", max_age=config.SESSION_HOURS * 3600, path="/")
    return {"user": user_json(user), "workspace": workspace_json(db, workspace)}


@app.get("/api/auth/me")
def me(user=Depends(current_user)):
    return user_json(user)


@app.post("/api/auth/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db), user=Depends(current_user)):
    token = request.cookies.get("mccia_session")
    db.query(LoginSession).filter_by(token_hash=token_hash(token)).delete(synchronize_session=False)
    audit(db, user, "logout")
    db.commit()
    response.delete_cookie("mccia_session", path="/")
    return {"success": True}


@app.post("/api/auth/password")
def change_password(body: PasswordInput, request: Request, db: Session = Depends(get_db), user=Depends(current_user)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "The current password is incorrect.")
    user.password_hash = hash_password(body.new_password)
    current_token_hash = token_hash(request.cookies["mccia_session"])
    db.query(LoginSession).filter(LoginSession.user_id == user.id, LoginSession.token_hash != current_token_hash).delete(synchronize_session=False)
    audit(db, user, "password_changed", details={"other_sessions_revoked": True})
    db.commit()
    return {"success": True, "message": "Password updated. Other sessions have been signed out."}


def workspace_json(db, workspace):
    counts = db.query(func.count(File.id), func.coalesce(func.sum(File.indexed_records), 0)).filter_by(workspace_id=workspace.id).one()
    return {"id": workspace.id, "name": workspace.name, "description": workspace.description, "color": workspace.color, "file_count": counts[0], "record_count": counts[1], "created_at": iso(workspace.created_at)}


@app.get("/api/workspaces")
def workspaces(db: Session = Depends(get_db), user=Depends(current_user)):
    return [workspace_json(db, w) for w in db.query(Workspace).filter(Workspace.id.in_(visible_workspace_ids(db, user))).order_by(Workspace.id)]


@app.post("/api/workspaces", status_code=201)
def create_workspace(body: WorkspaceInput, db: Session = Depends(get_db), user=Depends(require_admin)):
    workspace = Workspace(**body.model_dump())
    db.add(workspace)
    db.flush()
    db.add(Membership(workspace_id=workspace.id, user_id=user.id))
    audit(db, user, "workspace_created", workspace.id, details={"name": workspace.name})
    db.commit()
    return workspace_json(db, workspace)


@app.patch("/api/workspaces/{workspace_id}")
def rename_workspace(workspace_id: int, body: WorkspaceInput, db: Session = Depends(get_db), user=Depends(require_admin)):
    workspace = check_workspace(db, user, workspace_id)
    old_name = workspace.name
    for key, value in body.model_dump().items():
        setattr(workspace, key, value)
    audit(db, user, "workspace_updated", workspace.id, details={"previous_name": old_name, "name": workspace.name})
    db.commit()
    return workspace_json(db, workspace)


@app.delete("/api/workspaces/{workspace_id}")
def delete_workspace(workspace_id: int, db: Session = Depends(get_db), user=Depends(require_admin)):
    workspace = check_workspace(db, user, workspace_id)
    files = db.query(File).filter_by(workspace_id=workspace_id).all()
    if any(file.processing_status in {"uploaded", "processing"} for file in files):
        raise HTTPException(409, "Wait for document processing to finish before deleting this workspace.")
    paths = [storage_file(file) for file in files]
    audit(db, user, "workspace_deleted", workspace_id, details={"name": workspace.name, "files_deleted": len(files)})
    db.delete(workspace)
    db.commit()
    for path in paths:
        path.unlink(missing_ok=True)
    return {"success": True}


@app.get("/api/users")
def users(db: Session = Depends(get_db), user=Depends(require_admin)):
    return [user_json(item) for item in db.query(User).order_by(User.name)]


@app.post("/api/users", status_code=201)
def create_user(body: UserInput, db: Session = Depends(get_db), user=Depends(require_admin)):
    email = body.email.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HTTPException(422, "Enter a valid email address.")
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(409, "A user with this email already exists.")
    created = User(name=body.name.strip(), email=email, role=body.role, password_hash=hash_password(body.password))
    db.add(created)
    audit(db, user, "user_created", details={"email": email, "role": body.role})
    db.commit()
    return user_json(created)


@app.get("/api/workspaces/{workspace_id}/members")
def workspace_members(workspace_id: int, db: Session = Depends(get_db), user=Depends(require_admin)):
    check_workspace(db, user, workspace_id)
    return [user_json(member) for member in db.query(User).join(Membership, Membership.user_id == User.id).filter(Membership.workspace_id == workspace_id)]


@app.post("/api/workspaces/{workspace_id}/members")
def add_member(workspace_id: int, body: MembershipInput, db: Session = Depends(get_db), user=Depends(require_admin)):
    check_workspace(db, user, workspace_id)
    member = db.get(User, body.user_id)
    if not member:
        raise HTTPException(404, "User not found.")
    if not db.query(Membership).filter_by(workspace_id=workspace_id, user_id=member.id).first():
        db.add(Membership(workspace_id=workspace_id, user_id=member.id))
        audit(db, user, "workspace_member_added", workspace_id, details={"email": member.email})
        db.commit()
    return user_json(member)


@app.delete("/api/workspaces/{workspace_id}/members/{user_id}")
def remove_member(workspace_id: int, user_id: int, db: Session = Depends(get_db), user=Depends(require_admin)):
    check_workspace(db, user, workspace_id)
    db.query(Membership).filter_by(workspace_id=workspace_id, user_id=user_id).delete(synchronize_session=False)
    audit(db, user, "workspace_member_removed", workspace_id, details={"user_id": user_id})
    db.commit()
    return {"success": True}


@app.get("/api/files")
def files(workspace_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    check_workspace(db, user, workspace_id)
    return [file_json(db, file) for file in db.query(File).filter_by(workspace_id=workspace_id).order_by(File.uploaded_at.desc())]


@app.post("/api/files/upload", status_code=202)
def upload_files(background_tasks: BackgroundTasks, workspace_id: Annotated[int, Form()], files: Annotated[list[UploadFile], UploadFileField()], duplicate: Annotated[str, Form()] = "skip", source_type: Annotated[str, Form()] = "upload", category: Annotated[str, Form()] = "", last_modified: Annotated[str, Form()] = "[]", db: Session = Depends(get_db), user=Depends(require_editor)):
    check_workspace(db, user, workspace_id)
    if len(files) > 30:
        raise HTTPException(422, "Upload up to 30 files at a time.")
    if duplicate not in {"skip", "replace"}:
        raise HTTPException(422, "Duplicate handling must be skip or replace.")
    if source_type not in {"upload", "local_folder"}:
        raise HTTPException(422, "This source type is not connected.")
    if len(category) > 80:
        raise HTTPException(422, "Category must be 80 characters or fewer.")
    try:
        timestamps = json.loads(last_modified)
        if not isinstance(timestamps, list) or len(timestamps) > len(files):
            raise ValueError()
        modified_times = []
        for timestamp in timestamps:
            if timestamp is None:
                modified_times.append(None)
            elif isinstance(timestamp, (int, float)) and not isinstance(timestamp, bool):
                modified_times.append(datetime.fromtimestamp(timestamp / 1000, timezone.utc).replace(tzinfo=None))
            elif isinstance(timestamp, str):
                parsed_timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                modified_times.append(parsed_timestamp.astimezone(timezone.utc).replace(tzinfo=None) if parsed_timestamp.tzinfo else parsed_timestamp)
            else:
                raise ValueError()
    except (ValueError, TypeError, OverflowError, OSError):
        raise HTTPException(422, "last_modified must be a JSON array of ISO timestamps or browser millisecond timestamps in file order.")
    uploaded, skipped, errors = [], [], []
    for file_index, incoming in enumerate(files):
        filename = Path((incoming.filename or "file").replace("\\", "/")).name
        filename = re.sub(r"[\x00-\x1f<>:\"|?*]", "_", filename).strip(" .")[:255] or "file"
        extension = Path(filename).suffix.lower().lstrip(".")
        if extension not in config.ALLOWED_TYPES:
            errors.append({"filename": filename, "error": "Unsupported file type. Choose XLSX, CSV, PDF or PPTX."})
            incoming.file.close()
            continue
        key = f"{uuid.uuid4().hex}.{extension}"
        path = config.STORAGE_PATH / key
        size, checksum = 0, hashlib.sha256()
        try:
            with path.open("xb") as handle:
                while chunk := incoming.file.read(1024 * 1024):
                    size += len(chunk)
                    if size > config.MAX_UPLOAD_MB * 1024 * 1024:
                        raise ValueError(f"File exceeds the {config.MAX_UPLOAD_MB} MB upload limit.")
                    checksum.update(chunk)
                    handle.write(chunk)
            if not size:
                raise ValueError("The file is empty.")
            existing = db.query(File).filter_by(workspace_id=workspace_id, checksum=checksum.hexdigest()).first()
            if existing:
                path.unlink(missing_ok=True)
                if duplicate == "replace" and existing.processing_status not in {"processing", "uploaded"}:
                    job = ProcessingJob(file_id=existing.id)
                    existing.processing_status = "uploaded"
                    db.add(job)
                    db.flush()
                    audit(db, user, "reindex", workspace_id, existing, details={"duplicate": True})
                    db.commit()
                    background_tasks.add_task(process_file, existing.id, job.id)
                    uploaded.append(file_json(db, existing))
                else:
                    skipped.append({"filename": filename, "file_id": existing.id, "reason": "This file is already in the workspace."})
                    audit(db, user, "upload_duplicate", workspace_id, existing, status="skipped")
                    db.commit()
                continue
            file = File(workspace_id=workspace_id, filename=filename, file_type=extension, file_size=size, storage_key=key, checksum=checksum.hexdigest(), source_type=source_type, category=category, uploaded_by=user.id)
            if file_index < len(modified_times) and modified_times[file_index] is not None:
                file.last_modified = modified_times[file_index]
            db.add(file)
            db.flush()
            job = ProcessingJob(file_id=file.id)
            db.add(job)
            audit(db, user, "upload", workspace_id, file, details={"size": size, "source": source_type})
            db.commit()
            background_tasks.add_task(process_file, file.id, job.id)
            uploaded.append(file_json(db, file))
        except ValueError as exc:
            path.unlink(missing_ok=True)
            errors.append({"filename": filename, "error": str(exc)})
            audit(db, user, "upload", workspace_id, status="failed", details={"filename": filename, "error": str(exc)})
            db.commit()
        except IntegrityError:
            db.rollback()
            path.unlink(missing_ok=True)
            skipped.append({"filename": filename, "reason": "This file was uploaded by another request."})
        except Exception:
            db.rollback()
            path.unlink(missing_ok=True)
            raise
        finally:
            incoming.file.close()
    return {"files": uploaded, "uploaded": uploaded, "skipped": skipped, "errors": errors}


@app.get("/api/files/{file_id}")
def file_detail(file_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    return file_json(db, get_file(db, user, file_id))


@app.get("/api/files/{file_id}/records")
def file_records(file_id: int, limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db), user=Depends(current_user)):
    file = get_file(db, user, file_id)
    return [result_json(record, file) for record in db.query(SearchRecord).filter_by(file_id=file_id).order_by(SearchRecord.id).limit(limit)]


@app.get("/api/files/{file_id}/download")
def download_file(file_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    file = get_file(db, user, file_id)
    path = storage_file(file)
    if not path.is_file():
        raise HTTPException(404, "The original file is unavailable in storage.")
    audit(db, user, "download", file.workspace_id, file)
    db.commit()
    return FileResponse(path, filename=file.filename, media_type="application/octet-stream")


@app.post("/api/files/{file_id}/reindex", status_code=202)
def reindex_file(file_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db), user=Depends(require_editor)):
    file = get_file(db, user, file_id)
    if file.processing_status in {"uploaded", "processing"}:
        raise HTTPException(409, "This file is already being processed.")
    file.processing_status, file.error = "uploaded", None
    job = ProcessingJob(file_id=file.id)
    db.add(job)
    audit(db, user, "reindex", file.workspace_id, file)
    db.commit()
    background_tasks.add_task(process_file, file.id, job.id)
    return file_json(db, file)


@app.delete("/api/files/{file_id}")
def delete_file(file_id: int, db: Session = Depends(get_db), user=Depends(require_admin)):
    file = get_file(db, user, file_id)
    if file.processing_status in {"uploaded", "processing"}:
        raise HTTPException(409, "Wait for processing to finish before deleting this file.")
    path = storage_file(file)
    audit(db, user, "delete", file.workspace_id, file)
    db.delete(file)
    db.commit()
    path.unlink(missing_ok=True)
    return {"success": True}


@app.post("/api/search")
def search(body: SearchInput, db: Session = Depends(get_db), user=Depends(current_user)):
    check_workspace(db, user, body.workspace_id)
    response = run_search(db, body)
    filters = body.filters.model_dump(mode="json", exclude_none=True)
    db.add(SearchHistory(user_id=user.id, workspace_id=body.workspace_id, query=body.query, filters_json=filters, result_count=response["total_results"]))
    file_ids = [file_id for file_id, in db.query(File.id).filter_by(workspace_id=body.workspace_id, processing_status="indexed")]
    audit(db, user, "search", body.workspace_id, query=body.query, details={"filters": filters, "result_count": response["total_results"], "files_searched": file_ids, "matched_file_ids": list({item["file"]["id"] for item in response["results"]})})
    db.commit()
    return response


@app.get("/api/search/history")
def search_history(workspace_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    check_workspace(db, user, workspace_id)
    return [history_json(item) for item in db.query(SearchHistory).filter_by(workspace_id=workspace_id, user_id=user.id).order_by(SearchHistory.created_at.desc()).limit(20)]


def history_json(item):
    return {"id": item.id, "workspace_id": item.workspace_id, "query": item.query, "filters": item.filters_json, "result_count": item.result_count, "created_at": iso(item.created_at)}


def csv_safe(value):
    value = str(value if value is not None else "")
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "\n")) or value.startswith(("\t", "\r", "\n")) else value


@app.post("/api/search/export")
def export_search(body: SearchInput, db: Session = Depends(get_db), user=Depends(current_user)):
    check_workspace(db, user, body.workspace_id)
    results = run_search(db, body)
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["Query", "Result", "File", "File Type", "Location", "Score", "Timestamp"])
    for result in results["results"]:
        writer.writerow([csv_safe(value) for value in [body.query, result["value"], result["file"]["name"], result["file"]["type"], result["citation"]["text"], result["score"], results["searched_at"]]])
    audit(db, user, "export", body.workspace_id, query=body.query, details={"filters": results["filters"], "exported_results": len(results["results"]), "total_results": results["total_results"]})
    db.commit()
    return Response("\ufeff" + output.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="mccia-evidence.csv"', "X-Exported-Results": str(len(results["results"])), "X-Total-Results": str(results["total_results"])})


@app.get("/api/records/{record_id}/source")
def source(record_id: int, version: str | None = Query(default=None, max_length=80), db: Session = Depends(get_db), user=Depends(current_user)):
    record = db.get(SearchRecord, record_id)
    if not record:
        raise HTTPException(404, "This result is unavailable. The file may have been deleted or re-indexed.")
    file = get_file(db, user, record.file_id)
    if version is not None and version != iso(record.created_at):
        raise HTTPException(409, "This search result is from an earlier index. Run your search again to open the current source.")
    location = location_for(record)
    result = {"record": result_json(record, file), "file": file_json(db, file), "type": file.file_type, "location": location, "citation": result_json(record, file)["citation"], "headers": [], "rows": []}
    if file.file_type in {"xlsx", "csv"}:
        sheet_records = db.query(SearchRecord).filter(SearchRecord.file_id == file.id, SearchRecord.sheet_name == record.sheet_name)
        first_record = sheet_records.order_by(SearchRecord.id).first()
        headers = {header["key"]: header["label"] for header in first_record.metadata_json.get("table_headers", [])}
        for column, header in db.query(SearchRecord.column_name, SearchRecord.header).filter(SearchRecord.file_id == file.id, SearchRecord.sheet_name == record.sheet_name).distinct():
            headers.setdefault(column, header)
        ordered_columns = sorted(headers, key=column_index_from_string)
        header_row = first_record.metadata_json.get("header_row", 1)
        last_row = db.query(func.max(SearchRecord.row_number)).filter(SearchRecord.file_id == file.id, SearchRecord.sheet_name == record.sheet_name).scalar()
        first_row, final_row = max(header_row + 1, record.row_number - 3), min(last_row, record.row_number + 3)
        cells = sheet_records.filter(SearchRecord.row_number.between(first_row, final_row)).order_by(SearchRecord.row_number, SearchRecord.id).all()
        rows = {row_number: {"row_number": row_number, "cells": {column: {"coordinate": f"{column}{row_number}", "column": column, "header": headers[column], "value": "", "matched": False, "formula": None, "merged_range": None} for column in ordered_columns}} for row_number in range(first_row, final_row + 1)}
        for cell in cells:
            rows[cell.row_number]["cells"][cell.column_name] = {"coordinate": cell.cell_coordinate, "column": cell.column_name, "header": cell.header, "value": cell.value, "matched": cell.id == record.id, "formula": cell.metadata_json.get("formula"), "merged_range": cell.metadata_json.get("merged_range")}
        result["headers"] = [{"key": key, "label": headers[key]} for key in ordered_columns]
        result["rows"] = [{"row_number": row["row_number"], "cells": list(row["cells"].values())} for row in rows.values()]
    elif file.file_type == "pdf":
        page = db.query(PDFPage).filter_by(file_id=file.id, page_number=record.page_number).first()
        if page:
            result["page"] = {"page_number": page.page_number, "text": page.text, "width": page.width, "height": page.height, "bbox": record.metadata_json.get("bbox"), "image_url": f"/api/files/{file.id}/pages/{page.page_number}/image?record_id={record.id}"}
    elif file.file_type == "pptx":
        slide = db.query(PresentationSlide).filter_by(file_id=file.id, slide_number=record.slide_number).first()
        if slide:
            result["slide"] = {"slide_number": slide.slide_number, "title": slide.title, "content": slide.content, "notes": slide.notes}
    audit(db, user, "source_opened", file.workspace_id, file, location=citation_text(file, location), details={"record_id": record.id, "location": location})
    db.commit()
    return result


@app.get("/api/files/{file_id}/pages/{page_number}/image")
def pdf_image(file_id: int, page_number: int, record_id: int | None = None, db: Session = Depends(get_db), user=Depends(current_user)):
    file = get_file(db, user, file_id)
    if file.file_type != "pdf" or not storage_file(file).exists():
        raise HTTPException(404, "PDF source unavailable.")
    with fitz.open(storage_file(file)) as document:
        if not 1 <= page_number <= len(document):
            raise HTTPException(404, "Page not found.")
        page = document[page_number - 1]
        if record_id:
            record = db.get(SearchRecord, record_id)
            if record and record.file_id == file.id and record.page_number == page_number and record.metadata_json.get("bbox"):
                page.add_highlight_annot(fitz.Rect(record.metadata_json["bbox"]))
        scale = min(1.5, 1600 / max(page.rect.width, page.rect.height))
        image = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        return Response(image.tobytes("png"), media_type="image/png")


@app.get("/api/audit")
def audit_logs(workspace_id: int | None = None, limit: int = Query(200, ge=1, le=1000), db: Session = Depends(get_db), user=Depends(require_editor)):
    if workspace_id:
        check_workspace(db, user, workspace_id)
    query = db.query(AuditLog)
    if workspace_id:
        query = query.filter(AuditLog.workspace_id == workspace_id)
    elif user.role != "Admin":
        query = query.filter(AuditLog.workspace_id.in_(visible_workspace_ids(db, user)))
    return [{"id": item.id, "timestamp": iso(item.created_at), "created_at": iso(item.created_at), "user": item.user_name, "user_name": item.user_name, "action": item.action, "query": item.query, "file": item.file_name, "file_name": item.file_name, "file_id": item.file_id, "location": item.location, "status": item.status, "details": item.details_json} for item in query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit)]


@app.get("/api/dashboard")
def dashboard(workspace_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    check_workspace(db, user, workspace_id)
    files = db.query(File).filter_by(workspace_id=workspace_id).all()
    today = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    histories = db.query(SearchHistory).filter(SearchHistory.workspace_id == workspace_id)
    # Viewers can inspect document statistics, but only their own query history.
    if user.role == "Viewer":
        histories = histories.filter(SearchHistory.user_id == user.id)
    week = histories.filter(SearchHistory.created_at >= today - timedelta(days=6)).all()
    counts = Counter(item.created_at.date().isoformat() for item in week)
    stats = {"total_files": len(files), "indexed_files": sum(file.processing_status == "indexed" for file in files), "total_records": sum(file.indexed_records for file in files), "total_searchable_records": sum(file.indexed_records for file in files), "searches_today": sum(item.created_at >= today for item in week), "storage_used": sum(file.file_size for file in files), "storage_bytes": sum(file.file_size for file in files), "failed_jobs": db.query(ProcessingJob).join(File, File.id == ProcessingJob.file_id).filter(File.workspace_id == workspace_id, ProcessingJob.status == "failed").count()}
    access, searched = Counter(), Counter()
    events = db.query(AuditLog).filter(AuditLog.workspace_id == workspace_id, AuditLog.action.in_(["source_opened", "search"]))
    if user.role == "Viewer":
        events = events.filter(AuditLog.user_id == user.id)
    for event in events:
        if event.action == "source_opened" and event.file_id:
            access[event.file_id] += 1
        for file_id in event.details_json.get("matched_file_ids", []):
            searched[file_id] += 1
    names = {file.id: file.filename for file in files}
    ranked = lambda counts: [{"file_id": key, "name": names[key], "count": count} for key, count in counts.most_common(5) if key in names]
    return {"stats": stats, "files_by_type": [{"type": kind, "count": sum(file.file_type == kind for file in files)} for kind in ("xlsx", "csv", "pdf", "pptx")], "search_activity": [{"date": (today - timedelta(days=offset)).date().isoformat(), "count": counts[(today - timedelta(days=offset)).date().isoformat()]} for offset in range(6, -1, -1)], "recent_uploads": [file_json(db, file) for file in sorted(files, key=lambda file: file.uploaded_at, reverse=True)[:6]], "recent_searches": [history_json(item) for item in histories.order_by(SearchHistory.created_at.desc()).limit(6)], "most_searched_documents": ranked(searched), "most_accessed_sources": ranked(access)}


@app.get("/api/settings")
def settings(user=Depends(current_user)):
    return {"max_upload_mb": config.MAX_UPLOAD_MB, "allowed_file_types": sorted(config.ALLOWED_TYPES), "auto_index_on_upload": True, "storage_location": str(config.STORAGE_PATH) if user.role == "Admin" else "Private local storage", "search_result_limit": config.SEARCH_RESULT_LIMIT, "audit_retention_days": config.AUDIT_RETENTION_DAYS, "audit_retention_mode": "Configuration policy; records are retained until administrator-managed archival.", "database": engine.dialect.name, "session_hours": config.SESSION_HOURS, "folder_sync": "Manual browser folder import available; scheduled network sync requires a deployment-specific connector.", "google_drive": "Not connected. An administrator-managed OAuth connector is required.", "version": "1.0.0"}
