"""
Clear existing data and regenerate with enhanced realistic banking domain data
"""
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from app.core.database import get_engine
from app.database.data_generator import generate_all_data


def clear_all_data(db):
    """Clear all data from the 8 dimension tables"""
    tables = [
        'custom_freeze_details_dim',
        'gold_collateral_dim',
        'caselite_loan_applications',
        'super_loan_account_dim',
        'super_loan_dim',
        'account_ca_dim',
        'customer_non_individual_dim',
        'super_customer_dim'
    ]
    
    print("🗑️  Clearing existing data...")
    for table in tables:
        try:
            db.execute(text(f"DELETE FROM {table}"))
            print(f"   ✓ Cleared {table}")
        except Exception as e:
            print(f"   ⚠️  Could not clear {table}: {e}")
    
    db.commit()
    print("✅ All data cleared\n")


def main():
    """Clear and regenerate data"""
    print("🔄 Regenerating Enhanced Banking Domain Data...")
    print("=" * 60)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    db = SessionLocal()
    try:
        # Clear existing data
        clear_all_data(db)
        
        # Generate new enhanced data
        print("📝 Generating enhanced realistic data...")
        print("   - Realistic scheme names (LRGMI, SGL, MGL, AGRI, etc.)")
        print("   - Valid product types and categories")
        print("   - Proper constitution codes and descriptions")
        print("   - Date range distribution (30% stale data, 70% recent)")
        print("   - Realistic relationships between tables")
        print()
        
        generate_all_data(db)
        
        print("\n" + "=" * 60)
        print("✅ Data regeneration complete!")
        print("\n📊 Data Characteristics:")
        print("   - 30% of records have INSERTED_ON/LAST_UPDATED_TS from 3+ months ago")
        print("   - 70% of records are recent (within last 30 days)")
        print("   - Realistic banking domain values (schemes, products, codes)")
        print("   - Proper relationships and business logic")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()

