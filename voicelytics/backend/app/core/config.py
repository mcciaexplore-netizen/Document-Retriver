from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    database_url: str = 'postgresql+psycopg://voicelytics:voicelytics@localhost:5432/voicelytics'
    jwt_secret: str
    demo_password: str = ''
    cors_origins: str = 'http://localhost:5173,http://localhost:8080'
    upload_dir: str = '../uploads'
    smtp_host: str = ''
    smtp_port: int = 587
    smtp_user: str = ''
    smtp_password: str = ''
    smtp_from: str = ''
    smtp_tls: bool = True
    scheduler_enabled: bool = True
    model_config = SettingsConfigDict(env_file='../.env', extra='ignore')

    @field_validator('jwt_secret')
    @classmethod
    def strong_secret(cls, value):
        if len(value) < 32 or value.startswith('replace-with'):
            raise ValueError('JWT_SECRET must be a unique secret of at least 32 characters')
        return value


settings = Settings()
