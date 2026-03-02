from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Secure File Sharing API"
    database_url: str = "sqlite:///./app.db"
    signing_secret: str = Field(default="change-me-in-env", min_length=12)
    min_ttl_seconds: int = 60
    max_ttl_seconds: int = 86400 # 24 hours
    upload_root: str = "./data/uploads"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_")


settings = Settings()
