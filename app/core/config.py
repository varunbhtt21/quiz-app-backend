from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Database Configuration
    database_url: str = "sqlite:///./quiz_app.db"
    
    # JWT Configuration
    jwt_secret_key: str = "your-super-secret-jwt-key-change-this-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    
    # Application Configuration
    app_name: str = "Quiz App Backend"
    app_version: str = "1.0.0"
    debug: bool = True
    cors_origins: List[str] = [
        "http://localhost:8501", 
        "http://127.0.0.1:8501",
        "http://localhost:8080",
        "http://127.0.0.1:8080"
    ]
    
    # Email Configuration
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    from_email: str = ""
    
    # Frontend Configuration
    frontend_url: str = "http://localhost:8501"
    
    # Security
    bcrypt_rounds: int = 12

    class Config:
        env_file = ".env"


settings = Settings() 