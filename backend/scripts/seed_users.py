"""
Script to seed initial users in the database
"""
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_engine, get_db
from app.models.user import User
from app.services.auth import hash_password
from app.database.schema import Base
from datetime import datetime

def seed_users():
    """Seed initial users"""
    # Create tables if they don't exist
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    
    db = next(get_db())
    
    # Sample users to create
    users = [
        {
            "username": "admin.user",
            "email": "admin@bank.com",
            "password": "admin123",  # In production, use strong passwords
            "full_name": "Admin User",
            "role": "admin",
            "department": "IT Administration"
        },
        {
            "username": "approver.user",
            "email": "approver@bank.com",
            "password": "approver123",
            "full_name": "Approver User",
            "role": "approver",
            "department": "Risk Management"
        },
        {
            "username": "john.doe",
            "email": "john.doe@bank.com",
            "password": "user123",
            "full_name": "John Doe",
            "role": "user",
            "department": "Operations"
        },
        {
            "username": "jane.smith",
            "email": "jane.smith@bank.com",
            "password": "user123",
            "full_name": "Jane Smith",
            "role": "user",
            "department": "Compliance"
        }
    ]
    
    created_count = 0
    updated_count = 0
    skipped_count = 0
    
    for user_data in users:
        # Validate and clean password
        password = user_data["password"].strip()
        if len(password.encode('utf-8')) > 72:
            print(f"⚠️  Warning: Password for {user_data['username']} exceeds 72 bytes, truncating...")
            password_bytes = password.encode('utf-8')[:72]
            # Remove incomplete UTF-8 sequences
            while password_bytes and password_bytes[-1] & 0x80 and not (password_bytes[-1] & 0x40):
                password_bytes = password_bytes[:-1]
            password = password_bytes.decode('utf-8', errors='ignore')
        
        # Check if user already exists
        existing = db.query(User).filter(
            (User.USERNAME == user_data["username"]) | (User.EMAIL == user_data["email"])
        ).first()
        
        if existing:
            # Update existing user with password if it doesn't have one or is placeholder
            if not existing.PASSWORD_HASH or existing.PASSWORD_HASH == '$2b$12$DEFAULT_HASH_PLACEHOLDER':
                try:
                    existing.PASSWORD_HASH = hash_password(password)
                    existing.FULL_NAME = user_data["full_name"]
                    existing.ROLE = user_data["role"]
                    existing.DEPARTMENT = user_data["department"]
                    existing.IS_ACTIVE = True
                    db.commit()
                    print(f"🔄 Updated user: {user_data['username']} ({user_data['role']})")
                    updated_count += 1
                except Exception as e:
                    print(f"❌ Error updating user {user_data['username']}: {str(e)}")
                    db.rollback()
                    skipped_count += 1
            else:
                print(f"⏭️  User '{user_data['username']}' already exists with password, skipping...")
                skipped_count += 1
            continue
        
        # Create new user
        try:
            new_user = User(
                USERNAME=user_data["username"],
                EMAIL=user_data["email"],
                PASSWORD_HASH=hash_password(password),
                FULL_NAME=user_data["full_name"],
                ROLE=user_data["role"],
                DEPARTMENT=user_data["department"],
                IS_ACTIVE=True,
                CREATED_DATE=datetime.now()
            )
            
            db.add(new_user)
            created_count += 1
            print(f"✅ Created user: {user_data['username']} ({user_data['role']})")
        except Exception as e:
            print(f"❌ Error creating user {user_data['username']}: {str(e)}")
            db.rollback()
            skipped_count += 1
            continue
    
    try:
        db.commit()
    except Exception as e:
        print(f"❌ Error committing to database: {str(e)}")
        db.rollback()
        raise
    
    print(f"\n📊 Summary:")
    print(f"   Created: {created_count} users")
    print(f"   Updated: {updated_count} users")
    print(f"   Skipped: {skipped_count} users")
    print(f"\n🔑 Default passwords:")
    print(f"   Admin: admin123")
    print(f"   Approver: approver123")
    print(f"   Users: user123")
    print(f"\n⚠️  Remember to change these passwords in production!")

if __name__ == "__main__":
    print("🌱 Seeding users...")
    seed_users()
    print("✅ Done!")

