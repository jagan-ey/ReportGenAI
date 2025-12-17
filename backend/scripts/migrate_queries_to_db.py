"""
Migrate predefined queries from code to database
Run this once to populate the database with the 7 initial queries

Usage:
    cd backend
    # Activate your virtual environment first (e.g., genv\Scripts\activate)
    python scripts/migrate_queries_to_db.py
"""
import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import sessionmaker
from app.core.database import get_engine
from app.database.schema import PredefinedQueries
from app.services.predefined_queries import PREDEFINED_QUERIES


def migrate_queries_to_database():
    """Migrate hardcoded queries to database"""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    db = SessionLocal()
    
    try:
        print("🔄 Migrating predefined queries to database...")
        
        for key, query_data in PREDEFINED_QUERIES.items():
            # Check if query already exists
            existing = db.query(PredefinedQueries).filter(
                PredefinedQueries.QUERY_KEY == key
            ).first()
            
            if existing:
                print(f"  ⏭️  Query '{key}' already exists, skipping...")
                continue
            
            # Create query in database
            # No need for MATCH_KEYWORDS - we match directly against QUESTION field
            predefined_query = PredefinedQueries(
                QUERY_KEY=key,
                QUESTION=query_data["question"],
                SQL_QUERY=query_data["sql"].strip(),
                DESCRIPTION=query_data["description"],
                IS_ACTIVE=True,
                CREATED_DATE=datetime.now().date(),
                CREATED_BY="migration_script"
            )
            
            db.add(predefined_query)
            print(f"  ✅ Added query: {key}")
        
        db.commit()
        print("\n✅ Migration complete! All queries are now in the database.")
        print("\n💡 You can now manage queries through the database instead of code.")
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error during migration: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate_queries_to_database()

