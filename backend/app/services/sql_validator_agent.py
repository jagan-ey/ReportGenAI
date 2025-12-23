"""
SQL Validator Agent

Validates SQL queries against the actual database schema and corrects them if they fail.
This agent tries to execute the query (or validate column names) and uses error messages
to generate corrected SQL.
"""

from typing import Dict, Any, Optional, Tuple
import logging
import re

from sqlalchemy import text, inspect
from sqlalchemy.orm import Session

from app.core.config import settings

_logger = logging.getLogger(__name__)


class SQLValidatorAgent:
    """Validates and corrects SQL queries using database schema validation"""
    
    def __init__(self, db: Session):
        self.db = db
        self._llm = None
        self._initialized = False
        self._column_cache = {}  # Cache column names per table
    
    def _ensure_initialized(self):
        if self._initialized:
            return
        try:
            from langchain_openai import AzureChatOpenAI
            
            self._llm = AzureChatOpenAI(
                azure_endpoint=settings.AZURE_ENDPOINT,
                api_key=settings.OPENAI_API_KEY,
                api_version=settings.AZURE_API_VERSION,
                deployment_name=settings.AZURE_DEPLOYMENT_NAME,
                temperature=0.0,
            )
            self._initialized = True
        except Exception as e:
            _logger.warning(f"SQLValidator LLM not available: {e}")
            self._llm = None
            self._initialized = True
    
    def validate_and_correct(
        self,
        sql_query: str,
        original_question: str,
        schema_info: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validates SQL query and attempts to correct it if it fails.
        This is the safety net - it will ALWAYS attempt to fix SQLMaker errors.
        
        Returns:
            {
                "valid": bool,
                "corrected_sql": Optional[str],
                "error": Optional[str],
                "attempts": int
            }
        """
        # First, try basic validation
        validation_result = self._validate_sql_structure(sql_query)
        if not validation_result["valid"]:
            return validation_result
        
        # Try to validate against actual database schema
        schema_validation = self._validate_against_schema(sql_query)
        if schema_validation["valid"]:
            # Even if validation passes, check if there are obvious column errors or unnecessary joins
            # This catches cases where SQLMaker uses wrong table/column combinations or unnecessary joins
            obvious_errors = self._detect_obvious_column_errors(sql_query)
            if obvious_errors:
                _logger.info(f"Detected obvious column errors or unnecessary joins, attempting correction: {obvious_errors}")
                if self._llm:
                    correction_result = self._correct_sql_with_llm(
                        sql_query=sql_query,
                        error_message=f"Query optimization needed: {obvious_errors}. Consider simplifying by removing unnecessary joins.",
                        original_question=original_question,
                        schema_info=schema_info
                    )
                    # Re-validate the corrected SQL
                    if correction_result.get("corrected_sql"):
                        re_validation = self._validate_against_schema(correction_result["corrected_sql"])
                        if re_validation["valid"]:
                            return {
                                "valid": True,
                                "corrected_sql": correction_result["corrected_sql"],
                                "error": None,
                                "attempts": 1
                            }
            return {"valid": True, "corrected_sql": sql_query, "error": None, "attempts": 0}
        
        # If validation failed, ALWAYS try to correct using LLM
        # Use provided error_message if available (from execution), otherwise use schema validation error
        error_msg = error_message if error_message else schema_validation.get('error', 'Unknown error')
        _logger.info(f"SQL validation failed: {error_msg}, attempting correction...")
        if self._llm:
            correction_result = self._correct_sql_with_llm(
                sql_query=sql_query,
                error_message=error_msg,
                original_question=original_question,
                schema_info=schema_info
            )
            
            # If correction succeeded, validate it again
            if correction_result.get("corrected_sql"):
                re_validation = self._validate_against_schema(correction_result["corrected_sql"])
                if re_validation["valid"]:
                    return {
                        "valid": True,
                        "corrected_sql": correction_result["corrected_sql"],
                        "error": None,
                        "attempts": correction_result.get("attempts", 1)
                    }
                else:
                    # Correction didn't work, but return it anyway for execution to try
                    _logger.warning(f"Corrected SQL still has errors: {re_validation.get('error')}")
                    return {
                        "valid": False,
                        "corrected_sql": correction_result["corrected_sql"],
                        "error": re_validation.get("error", "Correction attempted but validation still fails"),
                        "attempts": correction_result.get("attempts", 1)
                    }
            
            return correction_result
        
        return {
            "valid": False,
            "corrected_sql": None,
            "error": schema_validation["error"],
            "attempts": 0
        }
    
    def _detect_obvious_column_errors(self, sql: str) -> Optional[str]:
        """
        Detect obvious column errors using actual schema validation.
        Completely generic - uses only database schema, no hardcoded values.
        """
        errors = []
        
        # Extract tables and columns from SQL
        tables = self._extract_tables(sql)
        columns_used = self._extract_columns(sql)
        
        # Check each column against actual schema
        invalid_columns = []
        for table, column in columns_used:
            # Skip unknown table (will be handled by error message parsing)
            if table == "unknown":
                continue
                
            if not self._column_exists(table, column):
                invalid_columns.append(f"{table}.{column}")
                # Try to find similar column names in the same table
                similar_columns = self._find_similar_columns(table, column)
                if similar_columns:
                    errors.append(f"{table} does not have {column}. Similar columns found: {', '.join(similar_columns)}")
        
        if invalid_columns:
            errors.append(f"Invalid columns detected: {', '.join(invalid_columns)}")
        
        return "; ".join(errors) if errors else None
    
    def _find_similar_columns(self, table_name: str, invalid_column: str, max_results: int = 5) -> list:
        """Find similar column names in the table using actual schema - completely generic"""
        try:
            # Get all columns for the table
            query = text("""
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = 'dbo'
                  AND TABLE_NAME = :table_name
                ORDER BY ORDINAL_POSITION
            """)
            
            all_columns = self.db.execute(query, {
                "table_name": table_name
            }).fetchall()
            
            if not all_columns:
                return []
            
            # Find similar columns using string matching
            invalid_upper = invalid_column.upper()
            similar = []
            
            for row in all_columns:
                col_name = row[0].upper()
                # Check for similarity
                if invalid_upper in col_name or col_name in invalid_upper:
                    # Exact match or contains
                    priority = 1 if col_name == invalid_upper else 2
                    similar.append((priority, row[0]))
                elif self._column_name_similarity(invalid_upper, col_name) > 0.5:
                    # Similar by edit distance
                    priority = 3
                    similar.append((priority, row[0]))
            
            # Sort by priority and return top results
            similar.sort(key=lambda x: x[0])
            return [col for _, col in similar[:max_results]]
            
        except Exception as e:
            _logger.warning(f"Error finding similar columns for {table_name}.{invalid_column}: {e}")
            return []
    
    def _column_name_similarity(self, col1: str, col2: str) -> float:
        """Simple similarity check - returns 0.0 to 1.0"""
        col1 = col1.upper()
        col2 = col2.upper()
        
        # Exact match
        if col1 == col2:
            return 1.0
        
        # One contains the other
        if col1 in col2 or col2 in col1:
            return 0.8
        
        # Check common substrings
        common_chars = set(col1) & set(col2)
        if len(common_chars) > len(col1) * 0.5:
            return 0.6
        
        return 0.0
    
    def _validate_sql_structure(self, sql: str) -> Dict[str, Any]:
        """Basic structural validation"""
        if not sql or not sql.strip():
            return {"valid": False, "error": "Empty SQL query"}
        
        sql_upper = sql.upper()
        
        # Must be a SELECT statement
        if "SELECT" not in sql_upper:
            return {"valid": False, "error": "Query must be a SELECT statement"}
        
        # Block dangerous operations
        dangerous_keywords = ["DROP", "DELETE", "TRUNCATE", "ALTER", "CREATE", "INSERT", "UPDATE"]
        for keyword in dangerous_keywords:
            if re.search(rf"\b{keyword}\b", sql_upper):
                return {"valid": False, "error": f"Dangerous operation detected: {keyword}"}
        
        return {"valid": True, "error": None}
    
    def _validate_against_schema(self, sql: str) -> Dict[str, Any]:
        """
        Validates SQL query against actual database schema by checking column names.
        Uses INFORMATION_SCHEMA to verify columns exist.
        """
        try:
            # Extract table and column names from SQL
            tables = self._extract_tables(sql)
            columns_used = self._extract_columns(sql)
            
            if not tables:
                return {"valid": True, "error": None}  # Can't validate without tables
            
            # Check each column against actual schema
            invalid_columns = []
            for table, column in columns_used:
                # Skip unknown table (will be handled by error message parsing)
                if table == "unknown":
                    continue
                    
                if not self._column_exists(table, column):
                    invalid_columns.append(f"{table}.{column}")
            
            if invalid_columns:
                error_msg = f"Invalid column names: {', '.join(invalid_columns)}"
                return {"valid": False, "error": error_msg}
            
            # Try a dry-run execution (with TOP 0 to avoid data retrieval)
            # This catches syntax errors and other runtime issues
            try:
                dry_run_sql = self._create_dry_run_query(sql)
                self.db.execute(text(dry_run_sql))
                return {"valid": True, "error": None}
            except Exception as e:
                error_str = str(e)
                # Extract meaningful error message
                if "Invalid column name" in error_str:
                    # Extract column name from error
                    col_match = re.search(r"Invalid column name '([^']+)'", error_str)
                    if col_match:
                        invalid_col = col_match.group(1)
                        # Try to find similar columns in the tables used
                        tables_in_query = self._extract_tables(sql)
                        suggestions = []
                        for table in tables_in_query:
                            similar = self._find_similar_columns(table, invalid_col, max_results=3)
                            if similar:
                                suggestions.append(f"{table}: {', '.join(similar)}")
                        
                        error_msg = f"Invalid column name: {invalid_col}"
                        if suggestions:
                            error_msg += f". Similar columns found: {'; '.join(suggestions)}"
                        return {"valid": False, "error": error_msg}
                return {"valid": False, "error": error_str}
        
        except Exception as e:
            _logger.warning(f"Schema validation error: {e}")
            # If validation itself fails, assume valid (fail open)
            return {"valid": True, "error": None}
    
    def _extract_tables(self, sql: str) -> list:
        """Extract table names from SQL"""
        tables = []
        # Match FROM and JOIN clauses, handling table aliases
        # Pattern: FROM table [AS] alias or JOIN table [AS] alias
        # Handle both "table alias" and "table AS alias" formats
        pattern = re.compile(
            r"\b(?:FROM|JOIN)\s+(?:\[?dbo\]?\.)?\[?(\w+)\]?\s+(?:AS\s+)?(\w+)",
            re.IGNORECASE
        )
        for match in pattern.finditer(sql):
            table = match.group(1)
            alias = match.group(2)
            # table is the actual table name, alias is optional
            if table and table.upper() not in ["SELECT", "WHERE", "GROUP", "ORDER", "HAVING"]:
                if alias and alias.upper() != "AS":
                    tables.append(table)
        
        # Also match tables without aliases
        pattern_no_alias = re.compile(
            r"\b(?:FROM|JOIN)\s+(?:\[?dbo\]?\.)?\[?(\w+)\]?(?:\s|$)",
            re.IGNORECASE
        )
        for match in pattern_no_alias.finditer(sql):
            table = match.group(1)
            if table and table.upper() not in ["SELECT", "WHERE", "GROUP", "ORDER", "HAVING", "AS"]:
                tables.append(table)
        
        return list(set(tables))  # Remove duplicates
    
    def _extract_columns(self, sql: str) -> list:
        """Extract (table, column) pairs from SQL"""
        columns = []
        
        # Extract table aliases (handle both "table alias" and "table AS alias")
        alias_pattern = re.compile(
            r"\b(?:FROM|JOIN)\s+(?:\[?dbo\]?\.)?\[?(\w+)\]?\s+(?:AS\s+)?(\w+)",
            re.IGNORECASE
        )
        aliases = {}
        for match in alias_pattern.finditer(sql):
            table = match.group(1)
            alias = match.group(2)
            if alias and alias.upper() != "AS":
                aliases[alias.lower()] = table
        
        # Extract column references (table.column or alias.column)
        # Pattern: word characters before and after dot
        col_pattern = re.compile(r"(\w+)\.(\w+)", re.IGNORECASE)
        for match in col_pattern.finditer(sql):
            prefix = match.group(1).lower()
            col = match.group(2)
            
            # Skip if this looks like a numeric literal (e.g., 0.6, 1.5, 100.25)
            # Both prefix and col being purely numeric indicates a decimal number, not table.column
            if prefix.isdigit() and col.isdigit():
                continue
            
            # Skip if prefix is purely numeric (e.g., 0.6 where prefix=0, col=6)
            # This catches decimal numbers where prefix is digits
            if prefix.isdigit():
                continue
            
            # Check if prefix is a table alias
            if prefix in aliases:
                table = aliases[prefix]
            else:
                # Check if prefix is an actual table name
                table = prefix
            
            # Skip if prefix is a SQL keyword
            if prefix.upper() not in ["AS", "SELECT", "FROM", "WHERE", "JOIN", "ON", "AND", "OR", "GROUP", "ORDER", "HAVING"]:
                columns.append((table, col))
        
        # Also extract unqualified column names from WHERE clause (e.g., WHERE column_name = 'value')
        # This catches cases where column is used without table prefix
        where_pattern = re.compile(r"WHERE\s+(.+?)(?:\s+ORDER\s+BY|\s*$)", re.IGNORECASE | re.DOTALL)
        where_match = where_pattern.search(sql)
        if where_match:
            where_clause = where_match.group(1)
            # Extract column names that appear before =, <, >, etc. (unqualified)
            unqualified_col_pattern = re.compile(r"\b([A-Z_][A-Z0-9_]*)\s*[=<>!]", re.IGNORECASE)
            tables_found = self._extract_tables(sql)
            for match in unqualified_col_pattern.finditer(where_clause):
                col_name = match.group(1)
                # Skip if this column was already captured with a table prefix
                if not any(t == table and c.upper() == col_name.upper() for t, c in columns):
                    # If we found tables in the query, try to match unqualified columns to those tables
                    if tables_found:
                        # For unqualified columns, check against all tables found
                        for table in tables_found:
                            columns.append((table, col_name))
                    else:
                        # If no tables found, still add it (will be validated later)
                        columns.append(("unknown", col_name))
        
        return columns
    
    def _column_exists(self, table_name: str, column_name: str) -> bool:
        """Check if a column exists in a table using INFORMATION_SCHEMA"""
        cache_key = f"{table_name}.{column_name}"
        if cache_key in self._column_cache:
            return self._column_cache[cache_key]
        
        try:
            query = text("""
                SELECT COUNT(*) 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = 'dbo' 
                  AND TABLE_NAME = :table_name 
                  AND COLUMN_NAME = :column_name
            """)
            result = self.db.execute(query, {
                "table_name": table_name,
                "column_name": column_name
            }).scalar()
            
            exists = result > 0
            self._column_cache[cache_key] = exists
            return exists
        except Exception as e:
            _logger.warning(f"Error checking column {table_name}.{column_name}: {e}")
            # If we can't check, assume it exists (fail open)
            return True
    
    def _create_dry_run_query(self, sql: str) -> str:
        """Create a dry-run query that validates syntax without returning data"""
        # Wrap in a subquery with TOP 0
        # This validates the query structure without executing it fully
        if "SELECT" in sql.upper():
            # Try to add TOP 0 if not already present
            if "TOP" not in sql.upper():
                # Handle DISTINCT properly - TOP must come after DISTINCT in SQL Server
                if re.search(r"SELECT\s+DISTINCT", sql, re.IGNORECASE):
                    # SELECT DISTINCT ... -> SELECT DISTINCT TOP 0 ...
                    sql = re.sub(r"SELECT\s+DISTINCT\s+", "SELECT DISTINCT TOP 0 ", sql, count=1, flags=re.IGNORECASE)
                else:
                    # SELECT ... -> SELECT TOP 0 ...
                    sql = re.sub(r"SELECT\s+", "SELECT TOP 0 ", sql, count=1, flags=re.IGNORECASE)
        return sql
    
    def _correct_sql_with_llm(
        self,
        sql_query: str,
        error_message: str,
        original_question: str,
        schema_info: Optional[str] = None
    ) -> Dict[str, Any]:
        """Use LLM to correct SQL based on error message"""
        self._ensure_initialized()
        if not self._llm:
            return {
                "valid": False,
                "corrected_sql": None,
                "error": error_message,
                "attempts": 0
            }
        
        # Get actual column names from database
        actual_columns = self._get_actual_columns_for_tables(sql_query)
        
        system_prompt = (
            "You are a SQL correction specialist. Your job is to fix SQL queries that have invalid column names.\n"
            "You MUST:\n"
            "- Fix column names to match the actual database schema provided\n"
            "- Return ONLY the corrected SQL query (no markdown, no explanations)\n"
            "- Use the exact column names from the schema information provided\n"
            "- Preserve the original query logic and structure\n"
            "- Use TOP (not LIMIT) for SQL Server\n"
            "- If a column doesn't exist, find the most similar column from the actual schema\n"
            "- If the error mentions a missing column, check the actual columns list and use the correct column name\n"
            "- Make intelligent corrections based on column name similarity and context\n"
        )
        
        user_prompt_parts = [
            f"Original question: {original_question}\n\n",
            f"SQL query with error:\n{sql_query}\n\n",
            f"Error message:\n{error_message}\n\n"
        ]
        
        if actual_columns:
            user_prompt_parts.append(f"Actual column names in database:\n{actual_columns}\n\n")
        
        if schema_info:
            user_prompt_parts.append(f"Schema information:\n{schema_info[:2000]}\n\n")
        
        user_prompt_parts.append(
            "CRITICAL: Use ONLY the actual column names from the schema provided above.\n"
            "If a column in the error message doesn't exist, find the most similar column name from the actual schema.\n"
            "Match columns based on:\n"
            "- Name similarity (e.g., 'invalid_col' might be 'valid_col' or 'similar_col')\n"
            "- Context (e.g., if looking for status, find status-related columns)\n"
            "- Data type (e.g., if filtering by date, use date columns)\n\n"
            "Preserve the original query intent while using correct column names.\n"
            "If a column doesn't exist and no similar column is found, remove that condition or use a different approach.\n\n"
            "Return ONLY the corrected SQL query:"
        )
        
        user_prompt = "".join(user_prompt_parts)
        
        try:
            from langchain_core.messages import SystemMessage, HumanMessage
            
            resp = self._llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ])
            
            corrected_sql = resp.content if hasattr(resp, "content") else str(resp)
            corrected_sql = self._clean_sql(corrected_sql)
            
            # Validate the corrected SQL
            validation = self._validate_against_schema(corrected_sql)
            if validation["valid"]:
                return {
                    "valid": True,
                    "corrected_sql": corrected_sql,
                    "error": None,
                    "attempts": 1
                }
            else:
                return {
                    "valid": False,
                    "corrected_sql": corrected_sql,
                    "error": validation["error"],
                    "attempts": 1
                }
        
        except Exception as e:
            _logger.error(f"Error correcting SQL with LLM: {e}")
            return {
                "valid": False,
                "corrected_sql": None,
                "error": f"LLM correction failed: {str(e)}",
                "attempts": 1
            }
    
    def _get_actual_columns_for_tables(self, sql: str) -> str:
        """Get actual column names for tables used in SQL"""
        tables = self._extract_tables(sql)
        if not tables:
            return ""
        
        columns_info = []
        for table in tables:
            try:
                query = text("""
                    SELECT COLUMN_NAME, DATA_TYPE
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = 'dbo'
                      AND TABLE_NAME = :table_name
                    ORDER BY ORDINAL_POSITION
                """)
                results = self.db.execute(query, {"table_name": table}).fetchall()
                if results:
                    cols = [f"{table}.{row[0]} ({row[1]})" for row in results]
                    columns_info.append(f"{table}:\n  " + "\n  ".join(cols))
            except Exception as e:
                _logger.warning(f"Error getting columns for {table}: {e}")
        
        return "\n\n".join(columns_info)
    
    def _clean_sql(self, sql: str) -> str:
        """Clean SQL from markdown and extract query"""
        if not sql:
            return ""
        
        # Remove markdown fences
        sql = re.sub(r"```sql\s*", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"```", "", sql)
        
        # Extract SQL starting from SELECT
        m = re.search(r"\bSELECT\b", sql, flags=re.IGNORECASE)
        if m:
            sql = sql[m.start():]
        
        # Take first statement
        parts = re.split(r";\s*\n|\n\s*\n", sql)
        sql = parts[0].strip() if parts else sql.strip()
        
        return sql.strip()

