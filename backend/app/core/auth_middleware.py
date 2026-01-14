"""
Authentication Middleware
Supports both username/password and SSO authentication based on configuration
"""
from fastapi import Depends, HTTPException, Header, Request
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
from app.services.auth import get_user_by_username
from app.services.sso_auth import (
    get_user_from_oauth2_token,
    get_user_from_proxy_headers
)

async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get current authenticated user
    Supports multiple authentication methods based on SSO_ENABLED flag
    """
    # SSO Authentication
    if settings.SSO_ENABLED:
        if settings.SSO_TYPE == "oauth2_oidc":
            # OAuth2/OIDC token validation
            if not authorization or not authorization.startswith("Bearer "):
                raise HTTPException(
                    status_code=401,
                    detail="Missing or invalid authorization header"
                )
            
            token = authorization.split(" ")[1]
            user_info = await get_user_from_oauth2_token(db, token)
            if not user_info:
                raise HTTPException(status_code=401, detail="Invalid or expired token")
            return user_info
        
        elif settings.SSO_TYPE == "proxy":
            # Reverse proxy authentication
            headers_dict = dict(request.headers)
            user_info = await get_user_from_proxy_headers(db, headers_dict)
            if not user_info:
                raise HTTPException(
                    status_code=401,
                    detail="Missing user identification from proxy headers"
                )
            return user_info
        
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Unsupported SSO type: {settings.SSO_TYPE}"
            )
    
    # Legacy username/password authentication
    else:
        if x_user_id:
            user = get_user_by_username(db, x_user_id)
            if user and user.IS_ACTIVE:
                return {
                    "user_id": user.USER_ID,
                    "username": user.USERNAME,
                    "email": user.EMAIL,
                    "role": user.ROLE,
                    "full_name": user.FULL_NAME,
                    "department": user.DEPARTMENT
                }
        
        # Default system user for development
        return {
            "user_id": 0,
            "username": "system",
            "email": "system@bank.com",
            "role": "user",
            "full_name": "System User",
            "department": None
        }
