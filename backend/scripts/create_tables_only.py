"""
Create database tables only (without test data)
Useful if you only want the schema, not the synthetic data
"""
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import init_db


def main():
    """Create tables only"""
    print("🚀 Creating database tables on SQL Server...")
    print("   Database: ey_digicube")
    print("   Server: IN3311064W1\\SQLSERVERDEV\n")
    
    try:
        init_db()
        print("\n✅ All tables created successfully!")
        print("\n📋 Created tables:")
        print("   1. super_customer_dim")
        print("   2. customer_non_individual_dim")
        print("   3. account_ca_dim")
        print("   4. super_loan_dim")
        print("   5. super_loan_account_dim")
        print("   6. caselite_loan_applications")
        print("   7. gold_collateral_dim")
        print("   8. custom_freeze_details_dim")
        print("\n💡 To add test data, run: python scripts/init_db.py")
    except Exception as e:
        print(f"\n❌ Error creating tables: {e}")
        print("\nPossible issues:")
        print("   - SQL Server not accessible")
        print("   - Wrong credentials")
        print("   - Database doesn't exist")
        print("   - Insufficient permissions")
        raise


if __name__ == "__main__":
    main()

