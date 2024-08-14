from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: str
    MAIL_PORT: int
    MAIL_SERVER: str
    MAIL_STARTTLS: bool  # Use MAIL_STARTTLS instead of MAIL_TLS
    MAIL_SSL_TLS: bool

    class Config:
        env_file = ".env"  # Ensure this points to the correct .env file

# Instantiate settings
conf = Settings()
