"""
Configuration settings for the application
"""
from pydantic_settings import BaseSettings
from pydantic import Field, AliasChoices
from typing import List


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "GenAI CCM Platform"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Azure OpenAI Configuration
    # Supports BOTH legacy env vars and the new AZURE_OPENAI_* env vars
    OPENAI_API_KEY: str = Field(
        default="",
        validation_alias=AliasChoices("AZURE_OPENAI_API_KEY", "OPENAI_API_KEY"),
    )
    AZURE_ENDPOINT: str = Field(
        default="",
        validation_alias=AliasChoices("AZURE_OPENAI_ENDPOINT", "AZURE_ENDPOINT"),
    )
    AZURE_DEPLOYMENT_NAME: str = Field(
        default="gpt-4o",
        validation_alias=AliasChoices("AZURE_OPENAI_CHAT_DEPLOYMENT", "AZURE_DEPLOYMENT_NAME"),
    )
    AZURE_API_VERSION: str = Field(
        default="2025-01-01-preview",
        validation_alias=AliasChoices("AZURE_OPENAI_API_VERSION", "AZURE_API_VERSION"),
    )
    LLM_TEMPERATURE: float = 0.0  # Low temperature for deterministic SQL generation
    
    # SQL Server Database
    DB_DRIVER: str = "ODBC Driver 17 for SQL Server"
    DB_SERVER: str = "IN3311064W1\\SQLSERVERDEV"
    DB_USERNAME: str = ""
    DB_PASSWORD: str = ""
    DB_NAME: str = "ey_digicube"
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    ALLOWED_HOSTS: List[str] = ["*"]
    
    # Query Settings
    MAX_QUERY_ROWS: int = 1000  # Limit query results
    QUERY_TIMEOUT: int = 30  # seconds (SQL Server may need more time)
    
    # BIU SPOC Contact Information
    BIU_SPOC_NAME: str = "BIU Support Team"
    BIU_SPOC_EMAIL: str = "biu.support@axisbank.com"
    BIU_SPOC_PHONE: str = "+91-22-2425-2525"
    BIU_SPOC_EXTENSION: str = "Ext. 1234"
    
    # Data Freshness Threshold (days)
    # Only ask about data freshness if lag_days exceeds this threshold
    DATA_FRESHNESS_THRESHOLD_DAYS: int = 3  # Default: 3 days
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

