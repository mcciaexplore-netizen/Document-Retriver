import logging
from pathlib import Path
from config import STORAGE_PATH
from database import SessionLocal
from models import File, ProcessingJob, SearchRecord, SpreadsheetCell, PDFPage, PresentationSlide, utcnow
from parsers import parse_file

logger = logging.getLogger(__name__)


def storage_file(file):
    path = (STORAGE_PATH / file.storage_key).resolve()
    if path.parent != STORAGE_PATH:
        raise ValueError("Invalid storage location.")
    return path


def process_file(file_id, job_id):
    with SessionLocal() as db:
        file = db.get(File, file_id)
        job = db.get(ProcessingJob, job_id)
        if not file or not job:
            return
        try:
            file.processing_status = "processing"
            job.status, job.progress = "processing", 15
            db.commit()
            records, pages, slides = parse_file(storage_file(file), file.file_type)
            job.progress = 60
            db.commit()
            db.query(SearchRecord).filter_by(file_id=file.id).delete(synchronize_session=False)
            db.query(PDFPage).filter_by(file_id=file.id).delete(synchronize_session=False)
            db.query(PresentationSlide).filter_by(file_id=file.id).delete(synchronize_session=False)
            for item in records:
                context = item.pop("context", "")
                normalized = " ".join([item["content"], file.filename, item.get("sheet_name") or "", context]).casefold()
                record = SearchRecord(workspace_id=file.workspace_id, file_id=file.id, normalized_content=normalized, **item)
                db.add(record)
                if record.record_type == "spreadsheet_cell":
                    db.flush()
                    metadata = record.metadata_json
                    db.add(SpreadsheetCell(record_id=record.id, formula=metadata.get("formula"), displayed_value=record.value, number_format=metadata.get("number_format"), merged_range=metadata.get("merged_range")))
            db.add_all(PDFPage(file_id=file.id, **page) for page in pages)
            db.add_all(PresentationSlide(file_id=file.id, **slide) for slide in slides)
            file.processing_status, file.indexed_records, file.error = "indexed", len(records), None
            job.status, job.progress, job.completed_at, job.error = "completed", 100, utcnow(), None
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning("Indexing failed for file %s: %s", file_id, type(exc).__name__)
            file, job = db.get(File, file_id), db.get(ProcessingJob, job_id)
            if file and job:
                message = str(exc) if isinstance(exc, ValueError) else "The document could not be parsed. Check that it is valid and not password protected."
                file.processing_status, file.error = "failed", message
                job.status, job.error, job.completed_at = "failed", message, utcnow()
                db.commit()
