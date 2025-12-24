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
    
    # SQL Server Database (Main Application Database)
    # NOTE: These are development defaults. In production, set via environment variables.
    DB_DRIVER: str = "ODBC Driver 17 for SQL Server"
    DB_SERVER: str = ""  # Set via DB_SERVER environment variable
    DB_USERNAME: str = ""
    DB_PASSWORD: str = ""
    DB_NAME: str = ""  # Set via DB_NAME environment variable
    
    # Knowledge Base Database (Regulatory Data Mart)
    # This is the database where the dimension tables are located (e.g., axis_reg_mart)
    # If not specified, defaults to main DB settings (for backward compatibility)
    KB_DB_SERVER: str = ""  # Set via KB_DB_SERVER environment variable (defaults to DB_SERVER if not set)
    KB_DB_NAME: str = ""  # Set via KB_DB_NAME environment variable (e.g., "axis_reg_mart" - the regulatory data mart database name)
    KB_DB_USERNAME: str = ""  # Set via KB_DB_USERNAME (defaults to DB_USERNAME if not set)
    KB_DB_PASSWORD: str = ""  # Set via KB_DB_PASSWORD (defaults to DB_PASSWORD if not set)
    KB_DB_DRIVER: str = "ODBC Driver 17 for SQL Server"  # Same driver as main DB
    
    # CORS
    # NOTE: Defaults are for development. In production, set CORS_ORIGINS via environment variable (comma-separated).
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]  # Dev defaults
    ALLOWED_HOSTS: List[str] = ["*"]
    
    # Query Settings
    MAX_QUERY_ROWS: int = 1000  # Limit query results
    QUERY_TIMEOUT: int = 30  # seconds (SQL Server may need more time)
    
    # BIU SPOC Contact Information
    # NOTE: These are generic defaults. Configure via environment variables for production.
    BIU_SPOC_NAME: str = "BIU Support Team"
    BIU_SPOC_EMAIL: str = "biu.support@bank.com"  # Generic default, configure via env var
    BIU_SPOC_PHONE: str = "+91-22-2425-2525"
    BIU_SPOC_EXTENSION: str = "Ext. 1234"
    
    # Data Freshness Threshold (days)
    # Only ask about data freshness if lag_days exceeds this threshold
    DATA_FRESHNESS_THRESHOLD_DAYS: int = 3  # Default: 3 days
    
    # Vector Knowledge Base Configuration
    VECTOR_DB_PATH: str = "backend/data/vector_db"  # Path to ChromaDB storage
    KNOWLEDGE_BASE_COLLECTION: str = "ccm_knowledge_base"  # ChromaDB collection name
    EMBEDDING_MODEL: str = "text-embedding-ada-002"  # Azure OpenAI embedding model
    EMBEDDING_DEPLOYMENT: str = "text-embedding-ada-002"  # Azure OpenAI embedding deployment
    KNOWLEDGE_CHUNK_SIZE: int = 1000  # Characters per chunk
    KNOWLEDGE_CHUNK_OVERLAP: int = 200  # Overlap between chunks
    MAX_RETRIEVAL_RESULTS: int = 5  # Max number of knowledge chunks to retrieve
    
    # Knowledge Base Document Paths
    BUSINESS_DOCS_PATH: str = "backend/data/business_docs"  # Path to business documents
    
    # SQL Agent Configuration
    # Comma-separated list of allowed tables for SQL agent (empty = all tables)
    # Example: "table1,table2,table3" or "" for all tables
    SQL_AGENT_ALLOWED_TABLES: str = ""  # Empty = allow all tables, or specify comma-separated list
    
    # Audit Column Names (for data freshness checks)
    # These are common audit column names used across tables
    # Comma-separated list, checked in order of preference
    AUDIT_COLUMNS: str = "LAST_UPDATED_TS,INSERTED_ON,UPDATED_DATE,CREATED_DATE,MODIFIED_DATE"  # Common audit column names
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

