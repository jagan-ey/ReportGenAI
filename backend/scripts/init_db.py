"""
Initialize database with schema and synthetic data
For SQL Server - creates tables if they don't exist
"""
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import sessionmaker
from app.core.database import init_db, get_engine
from app.database.data_generator import generate_all_data


def main():
    """Initialize database"""
    print("🚀 Initializing CCM POC Database on SQL Server...")
    
    # Create tables (if they don't exist)
    print("\n📊 Creating database tables (if not exists)...")
    try:
        init_db()
        print("✅ Tables created/verified")
    except Exception as e:
        print(f"⚠️  Table creation warning: {e}")
        print("   (Tables might already exist - continuing...)")
    
    # Generate synthetic data
    print("\n📝 Generating synthetic data...")
    print("   (This will add test data - existing data will remain)")
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    db = SessionLocal()
    try:
        generate_all_data(db)
        print("\n✅ Database initialization complete!")
    except Exception as e:
        print(f"\n❌ Error generating data: {e}")
        print("   (You can continue without synthetic data if tables already exist)")
    finally:
        db.close()


if __name__ == "__main__":
    main()

