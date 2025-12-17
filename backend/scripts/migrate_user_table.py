"""
Migration script to add PASSWORD_HASH and UPDATED_DATE columns to users table
"""
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import engine
from sqlalchemy import text

def migrate_user_table():
    """Add missing columns to users table"""
    print("🔄 Migrating users table...")
    
    try:
        with engine.connect() as conn:
            # Check if PASSWORD_HASH column exists
            check_password = text("""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'users' AND COLUMN_NAME = 'PASSWORD_HASH'
            """)
            result = conn.execute(check_password)
            has_password_hash = result.fetchone() is not None
            
            # Check if UPDATED_DATE column exists
            check_updated = text("""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'users' AND COLUMN_NAME = 'UPDATED_DATE'
            """)
            result = conn.execute(check_updated)
            has_updated_date = result.fetchone() is not None
            
            conn.commit()
            
            # Add PASSWORD_HASH column if it doesn't exist
            if not has_password_hash:
                print("  ➕ Adding PASSWORD_HASH column...")
                alter_password = text("""
                    ALTER TABLE users 
                    ADD PASSWORD_HASH VARCHAR(255) NULL
                """)
                conn.execute(alter_password)
                conn.commit()
                print("  ✅ PASSWORD_HASH column added")
            else:
                print("  ✓ PASSWORD_HASH column already exists")
            
            # Add UPDATED_DATE column if it doesn't exist
            if not has_updated_date:
                print("  ➕ Adding UPDATED_DATE column...")
                alter_updated = text("""
                    ALTER TABLE users 
                    ADD UPDATED_DATE DATETIME NULL
                """)
                conn.execute(alter_updated)
                conn.commit()
                print("  ✅ UPDATED_DATE column added")
            else:
                print("  ✓ UPDATED_DATE column already exists")
            
            # Update existing users to have a default password hash if PASSWORD_HASH is NULL
            # This is for existing users that don't have passwords set
            print("  🔄 Updating existing users...")
            update_null_passwords = text("""
                UPDATE users 
                SET PASSWORD_HASH = '$2b$12$DEFAULT_HASH_PLACEHOLDER'
                WHERE PASSWORD_HASH IS NULL
            """)
            result = conn.execute(update_null_passwords)
            updated_count = result.rowcount
            conn.commit()
            
            if updated_count > 0:
                print(f"  ⚠️  Found {updated_count} user(s) without passwords")
                print("  ⚠️  These users need to reset their passwords or be recreated")
            
            print("\n✅ Migration completed successfully!")
            print("\n📝 Next steps:")
            print("   1. Run: python scripts/seed_users.py")
            print("   2. This will create/update users with proper passwords")
            
    except Exception as e:
        print(f"❌ Error during migration: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    migrate_user_table()

