import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: str
    MAIL_PORT: int
    MAIL_SERVER: str
    MAIL_STARTTLS: bool
    MAIL_SSL_TLS: bool

    class Config:
        # Conditionally load the .env file if ENVIRONMENT is "development"
        env_file = ".env" if os.getenv("ENV") == "development" else None

# Instantiate settings
conf = Settings()
