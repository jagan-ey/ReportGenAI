"""
Authentication API endpoints
Supports both username/password and SSO authentication based on SSO_ENABLED flag
"""
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from pydantic import BaseModel, EmailStr
from typing import Optional
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
from app.services.auth import authenticate_user, hash_password, get_user_by_username
from app.services.sso_auth import (
    get_user_from_oauth2_token,
    get_user_from_proxy_headers,
    exchange_oauth2_code_for_token
)
from app.models.user import User
from datetime import datetime

router = APIRouter()


class LoginRequest(BaseModel):
    username: str  # Can be username or email
    password: str


class LoginResponse(BaseModel):
    status: str
    message: str
    user: dict
    token: Optional[str] = None  # For future JWT implementation


class CreateUserRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: str
    role: str = "user"  # user, approver, admin
    department: Optional[str] = None


class UpdateUserRequest(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    is_active: Optional[bool] = None


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate user with username/email and password
    Only available when SSO_ENABLED=False
    """
    if settings.SSO_ENABLED:
        raise HTTPException(
            status_code=400,
            detail="Username/password authentication is disabled. Please use SSO login."
        )
    
    try:
        user = authenticate_user(db, request.username, request.password)
        
        if not user:
            raise HTTPException(
                status_code=401,
                detail="Invalid username/email or password"
            )
        
        return {
            "status": "success",
            "message": "Login successful",
            "user": {
                "user_id": user.USER_ID,
                "username": user.USERNAME,
                "email": user.EMAIL,
                "full_name": user.FULL_NAME,
                "role": user.ROLE,
                "department": user.DEPARTMENT
            },
            "token": None
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during login: {str(e)}")


@router.post("/users")
async def create_user(
    request: CreateUserRequest,
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """
    Create a new user (requires admin role in production)
    For POC, allows any authenticated user
    """
    try:
        # Check if user already exists
        existing_user = get_user_by_username(db, request.username)
        if existing_user:
            raise HTTPException(status_code=400, detail="Username already exists")
        
        existing_email = db.query(User).filter(User.EMAIL == request.email).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="Email already exists")
        
        # Validate role
        if request.role not in ["user", "approver", "admin"]:
            raise HTTPException(status_code=400, detail="Invalid role. Must be: user, approver, or admin")
        
        # Create new user
        new_user = User(
            USERNAME=request.username,
            EMAIL=request.email,
            PASSWORD_HASH=hash_password(request.password),
            FULL_NAME=request.full_name,
            ROLE=request.role,
            DEPARTMENT=request.department,
            IS_ACTIVE=True,
            CREATED_DATE=datetime.now()
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        return {
            "status": "success",
            "message": "User created successfully",
            "user": {
                "user_id": new_user.USER_ID,
                "username": new_user.USERNAME,
                "email": new_user.EMAIL,
                "full_name": new_user.FULL_NAME,
                "role": new_user.ROLE,
                "department": new_user.DEPARTMENT
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating user: {str(e)}")


@router.get("/users")
async def list_users(
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """
    List all users (requires admin role in production)
    """
    try:
        users = db.query(User).filter(User.IS_ACTIVE == True).all()
        
        return {
            "users": [
                {
                    "user_id": u.USER_ID,
                    "username": u.USERNAME,
                    "email": u.EMAIL,
                    "full_name": u.FULL_NAME,
                    "role": u.ROLE,
                    "department": u.DEPARTMENT,
                    "is_active": u.IS_ACTIVE,
                    "created_date": u.CREATED_DATE.isoformat() if u.CREATED_DATE else None,
                    "last_login": u.LAST_LOGIN.isoformat() if u.LAST_LOGIN else None
                }
                for u in users
            ],
            "count": len(users)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching users: {str(e)}")


@router.get("/users/{user_id}")
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """
    Get user by ID
    """
    try:
        user = db.query(User).filter(User.USER_ID == user_id).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "user_id": user.USER_ID,
            "username": user.USERNAME,
            "email": user.EMAIL,
            "full_name": user.FULL_NAME,
            "role": user.ROLE,
            "department": user.DEPARTMENT,
            "is_active": user.IS_ACTIVE,
            "created_date": user.CREATED_DATE.isoformat() if user.CREATED_DATE else None,
            "last_login": user.LAST_LOGIN.isoformat() if user.LAST_LOGIN else None
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching user: {str(e)}")


@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    request: UpdateUserRequest,
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """
    Update user information (requires admin role or own account in production)
    """
    try:
        user = db.query(User).filter(User.USER_ID == user_id).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Update fields if provided
        if request.email is not None:
            # Check if email is already taken by another user
            existing = db.query(User).filter(
                User.EMAIL == request.email,
                User.USER_ID != user_id
            ).first()
            if existing:
                raise HTTPException(status_code=400, detail="Email already in use")
            user.EMAIL = request.email
        
        if request.full_name is not None:
            user.FULL_NAME = request.full_name
        
        if request.role is not None:
            if request.role not in ["user", "approver", "admin"]:
                raise HTTPException(status_code=400, detail="Invalid role")
            user.ROLE = request.role
        
        if request.department is not None:
            user.DEPARTMENT = request.department
        
        if request.is_active is not None:
            user.IS_ACTIVE = request.is_active
        
        user.UPDATED_DATE = datetime.now()
        
        db.commit()
        db.refresh(user)
        
        return {
            "status": "success",
            "message": "User updated successfully",
            "user": {
                "user_id": user.USER_ID,
                "username": user.USERNAME,
                "email": user.EMAIL,
                "full_name": user.FULL_NAME,
                "role": user.ROLE,
                "department": user.DEPARTMENT,
                "is_active": user.IS_ACTIVE
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating user: {str(e)}")


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """
    Delete (deactivate) a user (requires admin role in production)
    """
    try:
        user = db.query(User).filter(User.USER_ID == user_id).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Soft delete - set is_active to False
        user.IS_ACTIVE = False
        user.UPDATED_DATE = datetime.now()
        
        db.commit()
        
        return {
            "status": "success",
            "message": "User deactivated successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting user: {str(e)}")


# ============================================
# SSO Authentication Endpoints
# ============================================

class SSOCallbackRequest(BaseModel):
    code: str
    state: Optional[str] = None


@router.post("/sso/callback")
async def sso_callback(
    request: SSOCallbackRequest,
    db: Session = Depends(get_db)
):
    """
    Handle OAuth2/OIDC callback after SSO login
    Exchanges authorization code for tokens and returns user info
    """
    if not settings.SSO_ENABLED:
        raise HTTPException(
            status_code=400,
            detail="SSO is not enabled"
        )
    
    if settings.SSO_TYPE != "oauth2_oidc":
        raise HTTPException(
            status_code=400,
            detail="OAuth2/OIDC callback only available for oauth2_oidc SSO type"
        )
    
    try:
        # Exchange code for tokens
        token_data = await exchange_oauth2_code_for_token(request.code)
        if not token_data:
            raise HTTPException(
                status_code=401,
                detail="Failed to exchange authorization code for tokens"
            )
        
        # Get user from access token
        user_info = await get_user_from_oauth2_token(db, token_data["access_token"])
        if not user_info:
            raise HTTPException(
                status_code=401,
                detail="Failed to extract user information from token"
            )
        
        return {
            "status": "success",
            "message": "SSO login successful",
            "user": user_info,
            "token": token_data["access_token"],  # Return token for frontend
            "id_token": token_data.get("id_token"),
            "refresh_token": token_data.get("refresh_token")
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during SSO callback: {str(e)}")


@router.get("/sso/login-url")
async def get_sso_login_url():
    """
    Get SSO login URL for OAuth2/OIDC flow
    """
    if not settings.SSO_ENABLED:
        raise HTTPException(
            status_code=400,
            detail="SSO is not enabled"
        )
    
    if settings.SSO_TYPE != "oauth2_oidc":
        raise HTTPException(
            status_code=400,
            detail="Login URL only available for OAuth2/OIDC"
        )
    
    if not settings.SSO_AUTHORITY or not settings.SSO_CLIENT_ID:
        raise HTTPException(
            status_code=500,
            detail="SSO configuration incomplete"
        )
    
    # Build authorization URL
    auth_url = (
        f"{settings.SSO_AUTHORITY}/oauth2/v2.0/authorize?"
        f"client_id={settings.SSO_CLIENT_ID}&"
        f"response_type=code&"
        f"redirect_uri={settings.SSO_REDIRECT_URI}&"
        f"response_mode=query&"
        f"scope={settings.SSO_SCOPE}"
    )
    
    return {
        "login_url": auth_url,
        "sso_enabled": True,
        "sso_type": settings.SSO_TYPE
    }


@router.post("/sso/validate")
async def validate_sso_token(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    db: Session = Depends(get_db)
):
    """
    Validate SSO token and return user information
    Used by frontend to check if session is still valid
    """
    if not settings.SSO_ENABLED:
        raise HTTPException(
            status_code=400,
            detail="SSO is not enabled"
        )
    
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid authorization header"
        )
    
    token = authorization.split(" ")[1]
    
    try:
        if settings.SSO_TYPE == "oauth2_oidc":
            user_info = await get_user_from_oauth2_token(db, token)
            if not user_info:
                raise HTTPException(status_code=401, detail="Invalid token")
            return user_info
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Token validation not supported for SSO type: {settings.SSO_TYPE}"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error validating token: {str(e)}")

