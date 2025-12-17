"""
Query management endpoints
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_queries():
    """List available query endpoints"""
    return {
        "message": "Query management endpoints",
        "endpoints": [
            "/api/chat/query - Execute natural language query",
            "/api/chat/schema - Get database schema",
            "/api/chat/predefined - List predefined queries"
        ]
    }

