from abc import ABC, abstractmethod
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException, UploadFile
from app.core.config import settings

ALLOWED = {'.pdf': 'application/pdf', '.txt': 'text/plain', '.csv': 'text/csv', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webm': 'audio/webm', '.wav': 'audio/wav', '.ogg': 'audio/ogg', '.mp3': 'audio/mpeg', '.mp4': 'audio/mp4', '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}


class StorageService(ABC):
    @abstractmethod
    async def save(self, upload: UploadFile, audio: bool = False) -> tuple[str, str]: ...

    @abstractmethod
    def path(self, key: str) -> Path: ...


class LocalStorageService(StorageService):
    def path(self, key):
        root = Path(settings.upload_dir).resolve()
        target = (root / key).resolve()
        if target.parent != root:
            raise HTTPException(404, 'File not found')
        return target

    async def save(self, upload, audio=False):
        ext = Path(upload.filename or '').suffix.lower()
        if ext not in ALLOWED or (audio and not ALLOWED[ext].startswith('audio/')):
            raise HTTPException(422, 'Unsupported file type')
        data = await upload.read(25 * 1024 * 1024 + 1)
        if not data or len(data) > 25 * 1024 * 1024:
            raise HTTPException(413, 'File must be between 1 byte and 25 MB')
        signatures = {'.pdf': b'%PDF-', '.png': b'\x89PNG\r\n\x1a\n', '.jpg': b'\xff\xd8\xff', '.jpeg': b'\xff\xd8\xff', '.webm': b'\x1aE\xdf\xa3', '.wav': b'RIFF', '.ogg': b'OggS', '.docx': b'PK\x03\x04', '.xlsx': b'PK\x03\x04'}
        if ext in signatures and not data.startswith(signatures[ext]):
            raise HTTPException(422, 'File contents do not match its extension')
        if ext == '.mp4' and data[4:8] != b'ftyp':
            raise HTTPException(422, 'Invalid MP4 file')
        if ext == '.mp3' and not (data.startswith(b'ID3') or data[:1] == b'\xff'):
            raise HTTPException(422, 'Invalid MP3 file')
        if ext in {'.txt', '.csv'}:
            try:
                data.decode('utf-8-sig')
            except UnicodeDecodeError:
                raise HTTPException(422, 'Text files must use UTF-8 encoding')
        key = uuid4().hex + ext
        path = self.path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key, ALLOWED[ext]


storage = LocalStorageService()
