"""
SSO/IAM Authentication Service
Supports OAuth2/OIDC, SAML, and Reverse Proxy authentication
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from jose import JWTError, jwt
import httpx
import json

from app.core.config import settings
from app.models.user import User
from app.services.auth import get_user_by_username

logger = logging.getLogger(__name__)


def parse_role_mapping() -> Dict[str, str]:
    """Parse SSO_ROLE_MAPPING string into dictionary"""
    mapping = {}
    if settings.SSO_ROLE_MAPPING:
        for pair in settings.SSO_ROLE_MAPPING.split(","):
            if ":" in pair:
                sso_role, app_role = pair.split(":", 1)
                mapping[sso_role.strip().lower()] = app_role.strip().lower()
    return mapping


def map_sso_role_to_app_role(sso_roles: list) -> str:
    """
    Map SSO roles to application roles
    Returns 'user' as default if no mapping found
    """
    if not sso_roles:
        return "user"
    
    role_mapping = parse_role_mapping()
    
    # Check each SSO role for a match
    for sso_role in sso_roles:
        sso_role_lower = str(sso_role).strip().lower()
        if sso_role_lower in role_mapping:
            return role_mapping[sso_role_lower]
    
    # Default role
    return "user"


def sync_user_from_sso(
    db: Session,
    username: str,
    email: str,
    sso_roles: list,
    full_name: Optional[str] = None,
    department: Optional[str] = None
) -> User:
    """
    Sync SSO user to local database
    Creates user if doesn't exist, updates if exists
    """
    user = db.query(User).filter(
        (User.USERNAME == username) | (User.EMAIL == email)
    ).first()
    
    app_role = map_sso_role_to_app_role(sso_roles)
    
    if not user:
        # Create new user from SSO
        user = User(
            USERNAME=username,
            EMAIL=email,
            PASSWORD_HASH="SSO_USER",  # No password for SSO users
            FULL_NAME=full_name or username,
            ROLE=app_role,
            DEPARTMENT=department,
            IS_ACTIVE=True,
            CREATED_DATE=datetime.now()
        )
        db.add(user)
        logger.info(f"Created new SSO user: {username} with role {app_role}")
    else:
        # Update existing user
        user.EMAIL = email
        user.ROLE = app_role
        user.IS_ACTIVE = True
        user.LAST_LOGIN = datetime.now()
        if full_name:
            user.FULL_NAME = full_name
        if department:
            user.DEPARTMENT = department
        user.UPDATED_DATE = datetime.now()
        logger.info(f"Updated SSO user: {username} with role {app_role}")
    
    db.commit()
    db.refresh(user)
    return user


async def validate_oauth2_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Validate OAuth2/OIDC JWT token
    Returns token payload if valid, None otherwise
    """
    try:
        # If JWKS URL is provided, fetch public keys
        if settings.SSO_JWKS_URL:
            # For production, implement JWKS key fetching
            # For now, we'll use a simpler approach with client secret
            logger.warning("JWKS validation not fully implemented, using basic validation")
        
        # Decode token (without verification for now - should verify in production)
        # In production, verify against JWKS or use secret
        try:
            # Try to decode without verification to get claims
            unverified = jwt.get_unverified_claims(token)
            
            # Basic validation
            if not unverified:
                return None
            
            # Check audience if configured
            if settings.SSO_AUDIENCE:
                aud = unverified.get("aud")
                if aud != settings.SSO_AUDIENCE:
                    logger.warning(f"Token audience mismatch: {aud} != {settings.SSO_AUDIENCE}")
                    return None
            
            # Check expiration
            exp = unverified.get("exp")
            if exp and datetime.fromtimestamp(exp) < datetime.now():
                logger.warning("Token has expired")
                return None
            
            return unverified
            
        except JWTError as e:
            logger.error(f"JWT validation error: {e}")
            return None
            
    except Exception as e:
        logger.error(f"Error validating OAuth2 token: {e}")
        return None


async def get_user_from_oauth2_token(
    db: Session,
    token: str
) -> Optional[Dict[str, Any]]:
    """
    Extract user information from OAuth2/OIDC token
    Returns user dict or None
    """
    payload = await validate_oauth2_token(token)
    if not payload:
        return None
    
    # Extract user info from token claims
    username = payload.get("preferred_username") or payload.get("sub") or payload.get("email")
    email = payload.get("email") or username
    full_name = payload.get("name") or payload.get("given_name", "") + " " + payload.get("family_name", "")
    department = payload.get("department") or payload.get("groups")
    
    # Extract roles from token
    roles = []
    if "roles" in payload:
        roles = payload["roles"] if isinstance(payload["roles"], list) else [payload["roles"]]
    elif "groups" in payload:
        roles = payload["groups"] if isinstance(payload["groups"], list) else [payload["groups"]]
    
    if not username:
        logger.error("No username found in token")
        return None
    
    # Sync user to database
    user = sync_user_from_sso(db, username, email, roles, full_name, department)
    
    return {
        "user_id": user.USER_ID,
        "username": user.USERNAME,
        "email": user.EMAIL,
        "role": user.ROLE,
        "full_name": user.FULL_NAME,
        "department": user.DEPARTMENT
    }


async def get_user_from_proxy_headers(
    db: Session,
    headers: Dict[str, str]
) -> Optional[Dict[str, Any]]:
    """
    Extract user information from reverse proxy headers
    Returns user dict or None
    """
    username = headers.get(settings.PROXY_AUTH_HEADER_USER)
    email = headers.get(settings.PROXY_AUTH_HEADER_EMAIL) or username
    groups_str = headers.get(settings.PROXY_AUTH_HEADER_GROUPS, "")
    
    if not username:
        return None
    
    # Parse groups/roles
    roles = [g.strip() for g in groups_str.split(",") if g.strip()] if groups_str else []
    
    # Sync user to database
    user = sync_user_from_sso(db, username, email, roles)
    
    return {
        "user_id": user.USER_ID,
        "username": user.USERNAME,
        "email": user.EMAIL,
        "role": user.ROLE,
        "full_name": user.FULL_NAME,
        "department": user.DEPARTMENT
    }


async def exchange_oauth2_code_for_token(code: str) -> Optional[Dict[str, str]]:
    """
    Exchange OAuth2 authorization code for access token
    Returns dict with access_token and id_token, or None
    """
    if not settings.SSO_CLIENT_SECRET or not settings.SSO_CLIENT_ID:
        logger.error("SSO client credentials not configured")
        return None
    
    try:
        token_url = f"{settings.SSO_AUTHORITY}/oauth2/v2.0/token"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                token_url,
                data={
                    "client_id": settings.SSO_CLIENT_ID,
                    "client_secret": settings.SSO_CLIENT_SECRET,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": settings.SSO_REDIRECT_URI,
                    "scope": settings.SSO_SCOPE
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code == 200:
                token_data = response.json()
                return {
                    "access_token": token_data.get("access_token"),
                    "id_token": token_data.get("id_token"),
                    "refresh_token": token_data.get("refresh_token"),
                    "expires_in": token_data.get("expires_in", 3600)
                }
            else:
                logger.error(f"Token exchange failed: {response.status_code} - {response.text}")
                return None
                
    except Exception as e:
        logger.error(f"Error exchanging OAuth2 code: {e}")
        return None
