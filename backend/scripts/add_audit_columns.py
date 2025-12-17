"""
Add audit timestamp columns to the 8 BIU tables in SQL Server.

This is needed because SQLAlchemy create_all() does NOT add new columns to existing tables.

Adds (if missing):
- INSERTED_ON (DATETIME2)
- LAST_UPDATED_TS (DATETIME2)
"""

import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.core.database import get_engine


TABLES = [
    "super_customer_dim",
    "customer_non_individual_dim",
    "account_ca_dim",
    "super_loan_dim",
    "super_loan_account_dim",
    "caselite_loan_applications",
    "gold_collateral_dim",
    "custom_freeze_details_dim",
]

AUDIT_COLUMNS = [
    ("INSERTED_ON", "DATETIME2 NULL"),
    ("LAST_UPDATED_TS", "DATETIME2 NULL"),
]


def column_exists(conn, table_name: str, column_name: str) -> bool:
    q = text(
        """
        SELECT 1
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = 'dbo'
          AND TABLE_NAME = :table_name
          AND COLUMN_NAME = :column_name
        """
    )
    return conn.execute(q, {"table_name": table_name, "column_name": column_name}).first() is not None


def main():
    engine = get_engine()
    with engine.begin() as conn:
        for table in TABLES:
            print(f"\n🔧 Checking table: {table}")
            for col, ddl in AUDIT_COLUMNS:
                if column_exists(conn, table, col):
                    print(f"  ✅ {col} exists")
                    continue
                print(f"  ➕ Adding {col}...")
                conn.execute(text(f"ALTER TABLE dbo.{table} ADD {col} {ddl}"))
                print(f"  ✅ Added {col}")

    print("\n✅ Audit columns migration complete.")


if __name__ == "__main__":
    main()


