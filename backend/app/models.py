from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey, JSON, UniqueConstraint
from .database import Base


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    email = Column(String(254), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(20), nullable=False, default="Viewer")
    created_at = Column(DateTime, default=utcnow, nullable=False)


class LoginSession(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at = Column(DateTime, nullable=False)


class Workspace(Base):
    __tablename__ = "workspaces"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    description = Column(String(500), default="")
    color = Column(String(20), default="teal")
    created_at = Column(DateTime, default=utcnow, nullable=False)


class Membership(Base):
    __tablename__ = "workspace_memberships"
    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    __table_args__ = (UniqueConstraint("workspace_id", "user_id"),)


class File(Base):
    __tablename__ = "files"
    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True, nullable=False)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(10), nullable=False)
    file_size = Column(Integer, nullable=False)
    storage_key = Column(String(80), nullable=False)
    checksum = Column(String(64), nullable=False)
    source_type = Column(String(40), default="upload", nullable=False)
    category = Column(String(80), default="")
    processing_status = Column(String(20), default="uploaded", nullable=False)
    indexed_records = Column(Integer, default=0, nullable=False)
    error = Column(Text)
    uploaded_at = Column(DateTime, default=utcnow, nullable=False)
    last_modified = Column(DateTime, default=utcnow, nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    __table_args__ = (UniqueConstraint("workspace_id", "checksum", name="uq_files_workspace_checksum"),)


class ProcessingJob(Base):
    __tablename__ = "file_processing_jobs"
    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey("files.id", ondelete="CASCADE"), index=True, nullable=False)
    status = Column(String(20), default="queued", nullable=False)
    progress = Column(Integer, default=0, nullable=False)
    error = Column(Text)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    completed_at = Column(DateTime)


class SearchRecord(Base):
    __tablename__ = "document_chunks"
    __table_args__ = {"sqlite_autoincrement": True}
    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True, nullable=False)
    file_id = Column(Integer, ForeignKey("files.id", ondelete="CASCADE"), index=True, nullable=False)
    record_type = Column(String(30), nullable=False)
    content = Column(Text, nullable=False)
    normalized_content = Column(Text, nullable=False)
    value = Column(Text, nullable=False)
    header = Column(String(500))
    numeric_value = Column(Float, index=True)
    metadata_json = Column(JSON, default=dict, nullable=False)
    sheet_name = Column(String(255), index=True)
    row_number = Column(Integer)
    column_name = Column(String(255))
    cell_coordinate = Column(String(30))
    page_number = Column(Integer)
    slide_number = Column(Integer)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class SpreadsheetCell(Base):
    __tablename__ = "spreadsheet_cells"
    id = Column(Integer, primary_key=True)
    record_id = Column(Integer, ForeignKey("document_chunks.id", ondelete="CASCADE"), unique=True, nullable=False)
    formula = Column(Text)
    displayed_value = Column(Text)
    number_format = Column(String(255))
    merged_range = Column(String(80))


class PDFPage(Base):
    __tablename__ = "pdf_pages"
    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey("files.id", ondelete="CASCADE"), index=True, nullable=False)
    page_number = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    width = Column(Float)
    height = Column(Float)


class PresentationSlide(Base):
    __tablename__ = "presentation_slides"
    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey("files.id", ondelete="CASCADE"), index=True, nullable=False)
    slide_number = Column(Integer, nullable=False)
    title = Column(Text)
    content = Column(Text)
    notes = Column(Text)


class SearchHistory(Base):
    __tablename__ = "search_history"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True, nullable=False)
    query = Column(Text, nullable=False)
    filters_json = Column(JSON, default=dict, nullable=False)
    result_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    user_name = Column(String(120), nullable=False)
    workspace_id = Column(Integer, index=True)
    action = Column(String(60), nullable=False)
    query = Column(Text, default="")
    file_id = Column(Integer)
    file_name = Column(String(255), default="")
    location = Column(String(500), default="")
    status = Column(String(20), default="success")
    details_json = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
