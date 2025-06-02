from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Database Configuration
    database_url: str = "postgresql://postgres:password@localhost/quiz_app"
    direct_url: str = ""  # Direct connection URL for migrations/admin operations
    
    # Supabase Configuration
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_storage_bucket: str = "quiz-images"
    
    # JWT Configuration
    jwt_secret_key: str = "your-super-secret-jwt-key-change-this-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    
    # OTPLESS Configuration
    otpless_app_id: str = ""
    otpless_client_id: str = ""
    otpless_client_secret: str = ""
    otpless_webhook_secret: str = ""
    
    # Application Configuration
    app_name: str = "QuizMaster by Jazzee"
    app_version: str = "1.0.0"
    debug: bool = True
    # cors_origins: List[str] = [
    #     "http://localhost:5173", 
    #     "http://127.0.0.1:5173",
    #     "http://localhost:8501", 
    #     "http://127.0.0.1:8501"
    # ]

        # CORS Configuration - store as string, parse as needed
    cors_origins_str: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8501,http://127.0.0.1:8501"
    
    @property
    def cors_origins(self) -> List[str]:
        """Parse CORS origins string into a list"""
        return [origin.strip() for origin in self.cors_origins_str.split(',') if origin.strip()]
    
    
    # Email Configuration
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    from_email: str = ""
    
    # Frontend Configuration
    frontend_url: str = "http://localhost:5173"
    
    # Security
    bcrypt_rounds: int = 12

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings() 