"""
Authentication and password hashing utilities
"""
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.user import User
import hashlib
import secrets

# Try to use bcrypt, fallback to SHA256 if it fails
try:
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    USE_BCRYPT = True
except Exception as e:
    print(f"Warning: bcrypt not available, using SHA256 fallback: {e}")
    pwd_context = None
    USE_BCRYPT = False


def hash_password(password: str) -> str:
    """Hash a password using bcrypt (or SHA256 fallback)"""
    # Ensure password is a string and strip whitespace
    if not isinstance(password, str):
        password = str(password)
    password = password.strip()
    
    # Try bcrypt first
    if USE_BCRYPT and pwd_context:
        try:
            # Bcrypt has a 72-byte limit - check byte length
            password_bytes = password.encode('utf-8')
            if len(password_bytes) > 72:
                # Truncate to 72 bytes safely
                password_bytes = password_bytes[:72]
                # Remove incomplete UTF-8 sequences
                while password_bytes and (password_bytes[-1] & 0xC0) == 0x80:
                    password_bytes = password_bytes[:-1]
                password = password_bytes.decode('utf-8', errors='ignore')
            
            return pwd_context.hash(password)
        except (ValueError, AttributeError, Exception) as e:
            print(f"Warning: bcrypt hashing failed, using SHA256 fallback: {e}")
    
    # Fallback: use SHA256 with salt (for POC only, NOT production-ready)
    salt = secrets.token_hex(16)
    hash_obj = hashlib.sha256((password + salt).encode('utf-8'))
    return f"sha256${salt}${hash_obj.hexdigest()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    if not plain_password or not hashed_password:
        return False
    
    # Strip whitespace from password to match hash_password behavior
    plain_password = str(plain_password).strip()
    
    # Handle SHA256 fallback hashes
    if hashed_password.startswith("sha256$"):
        try:
            parts = hashed_password.split("$")
            if len(parts) == 3:
                salt = parts[1]
                stored_hash = parts[2]
                hash_obj = hashlib.sha256((plain_password + salt).encode('utf-8'))
                return hash_obj.hexdigest() == stored_hash
        except Exception:
            return False
    
    # Try bcrypt verification
    if USE_BCRYPT and pwd_context:
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except (ValueError, AttributeError, Exception):
            return False
    
    return False


def authenticate_user(db: Session, username: str, password: str) -> User:
    """
    Authenticate a user by username/email and password
    Returns User object if authentication succeeds, None otherwise
    """
    # Strip whitespace from inputs
    username = str(username).strip()
    password = str(password).strip()
    
    # Try to find user by username or email
    user = db.query(User).filter(
        (User.USERNAME == username) | (User.EMAIL == username)
    ).first()
    
    if not user:
        return None
    
    if not user.IS_ACTIVE:
        return None
    
    if not verify_password(password, user.PASSWORD_HASH):
        return None
    
    # Update last login
    user.LAST_LOGIN = datetime.now()
    db.commit()
    
    return user


def get_user_by_username(db: Session, username: str) -> User:
    """Get user by username or email"""
    return db.query(User).filter(
        (User.USERNAME == username) | (User.EMAIL == username)
    ).first()


def get_user_by_id(db: Session, user_id: int) -> User:
    """Get user by ID"""
    return db.query(User).filter(User.USER_ID == user_id).first()
