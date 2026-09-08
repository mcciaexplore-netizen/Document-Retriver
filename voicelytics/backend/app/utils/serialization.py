from datetime import datetime


def record(obj):
    if obj is None:
        return None
    result = {}
    for column in obj.__table__.columns:
        if column.name in {'password_hash', 'key_hash', 'file_path'}:
            continue
        value = getattr(obj, column.name)
        result[column.name] = value.isoformat() + 'Z' if isinstance(value, datetime) else value
    return result
