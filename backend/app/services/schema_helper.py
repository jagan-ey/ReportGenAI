"""
Schema Helper Utilities
Provides generic, schema-driven utilities for getting table and column information
"""
from typing import List, Dict, Optional
import logging
from sqlalchemy import text, inspect
from sqlalchemy.engine import Engine

_logger = logging.getLogger(__name__)


def get_all_tables(engine: Engine, schema: str = "dbo") -> List[str]:
    """
    Get all table names from the database schema dynamically.
    Completely generic - works for any database.
    
    Args:
        engine: SQLAlchemy engine
        schema: Schema name (default: 'dbo' for SQL Server)
    
    Returns:
        List of table names
    """
    try:
        query = text("""
            SELECT TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = :schema
              AND TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_NAME
        """)
        
        with engine.connect() as conn:
            results = conn.execute(query, {"schema": schema}).fetchall()
            tables = [row[0] for row in results]
            _logger.debug(f"Found {len(tables)} tables in schema '{schema}'")
            return tables
    except Exception as e:
        _logger.warning(f"Error getting tables from schema: {e}")
        return []


def get_table_columns(engine: Engine, table_name: str, schema: str = "dbo") -> List[Dict[str, str]]:
    """
    Get all columns for a specific table dynamically.
    Completely generic - works for any table.
    
    Args:
        engine: SQLAlchemy engine
        table_name: Table name
        schema: Schema name (default: 'dbo' for SQL Server)
    
    Returns:
        List of dicts with column info: [{"name": "COLUMN_NAME", "type": "DATA_TYPE", "nullable": "YES/NO"}, ...]
    """
    try:
        query = text("""
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = :schema
              AND TABLE_NAME = :table_name
            ORDER BY ORDINAL_POSITION
        """)
        
        with engine.connect() as conn:
            results = conn.execute(query, {"schema": schema, "table_name": table_name}).fetchall()
            columns = [
                {
                    "name": row[0],
                    "type": row[1],
                    "nullable": row[2] == "YES"
                }
                for row in results
            ]
            return columns
    except Exception as e:
        _logger.warning(f"Error getting columns for table {table_name}: {e}")
        return []


def get_tables_from_sql(sql: str) -> List[str]:
    """
    Extract table names from SQL query.
    Generic - works for any SQL query.
    
    Args:
        sql: SQL query string
    
    Returns:
        List of unique table names found in the query
    """
    import re
    
    if not sql:
        return []
    
    # Remove markdown fences
    sql = re.sub(r"```sql\s*|\s*```", "", sql, flags=re.IGNORECASE).strip()
    
    tables = []
    # Match FROM and JOIN clauses
    pattern = re.compile(
        r"\b(?:FROM|JOIN)\s+(?:\[?dbo\]?\.)?\[?(\w+)\]?",
        re.IGNORECASE
    )
    
    for match in pattern.finditer(sql):
        table = match.group(1)
        if table and table.upper() not in ["SELECT", "WHERE", "GROUP", "ORDER", "HAVING", "AS"]:
            tables.append(table)
    
    return list(set(tables))  # Remove duplicates

