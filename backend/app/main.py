"""
FastAPI Main Application
GenAI-Based CCM Platform Backend
"""
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
import uvicorn

from app.api import chat, health, reports, auth
from app.core.config import settings
from app.core.database import get_engine
from app.database.schema import Base
from app.models import user  # Import user models to ensure tables are created
from app.core.logging import setup_logging

# Setup logging
logger = setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting GenAI CCM Platform...")
    # Create database tables (if they don't exist)
    # Note: This is safe - SQLAlchemy won't recreate existing tables
    # Run in background to avoid blocking startup
    import asyncio
    import concurrent.futures
    
    def init_tables():
        try:
            engine = get_engine()
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables initialized/verified")
        except Exception as e:
            logger.warning(f"Table creation check failed: {e}")
            logger.info("Continuing - tables may already exist or need manual creation")
    
    # Run table initialization in thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as executor:
        try:
            # Set a timeout to prevent hanging
            await asyncio.wait_for(
                loop.run_in_executor(executor, init_tables),
                timeout=10.0
            )
        except asyncio.TimeoutError:
            logger.warning("Table initialization timed out - continuing anyway")
        except Exception as e:
            logger.warning(f"Table initialization error: {e} - continuing anyway")
    
    yield
    
    # Shutdown
    logger.info("Shutting down GenAI CCM Platform...")


# Initialize FastAPI app
app = FastAPI(
    title="GenAI CCM Platform API",
    description="Continuous Controls Monitoring Platform with GenAI capabilities",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security Middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.ALLOWED_HOSTS
)

# Include routers
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "GenAI CCM Platform API",
        "version": "1.0.0",
        "status": "operational"
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )

