"""
SQL Validator Agent

Validates SQL queries against the actual database schema and corrects them if they fail.
This agent tries to execute the query (or validate column names) and uses error messages
to generate corrected SQL.
"""

from typing import Dict, Any, Optional, Tuple
import logging
import re
import os
from datetime import datetime

from sqlalchemy import text, inspect
from sqlalchemy.orm import Session

from app.core.config import settings

# Setup dedicated logger for SQL validator debugging
_log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')
os.makedirs(_log_dir, exist_ok=True)

_log_file = os.path.join(_log_dir, f'sql_validator_debug_{datetime.now().strftime("%Y%m%d")}.log')
_validator_file_handler = logging.FileHandler(_log_file, mode='a', encoding='utf-8')
_validator_file_handler.setLevel(logging.DEBUG)

_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
_validator_file_handler.setFormatter(_formatter)

# Create validator logger
_validator_logger = logging.getLogger('sql_validator_debug')
_validator_logger.setLevel(logging.DEBUG)
# Don't clear handlers - we want to share with chat.py logger
if not any(isinstance(h, logging.FileHandler) and h.baseFilename == _log_file for h in _validator_logger.handlers):
    _validator_logger.addHandler(_validator_file_handler)
if settings.DEBUG:
    if not any(isinstance(h, logging.StreamHandler) for h in _validator_logger.handlers):
        _validator_logger.addHandler(logging.StreamHandler())

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
            _validator_logger.debug("LLM already initialized")
            return
        try:
            _validator_logger.info("📝 Initializing LLM for SQL Validator...")
            from langchain_openai import AzureChatOpenAI
            
            # Get config values - settings uses AliasChoices so both names should work
            # But check if values are empty and try alternative access
            azure_endpoint = settings.AZURE_ENDPOINT if settings.AZURE_ENDPOINT else ''
            api_key = settings.OPENAI_API_KEY if settings.OPENAI_API_KEY else ''
            api_version = settings.AZURE_API_VERSION if settings.AZURE_API_VERSION else '2025-01-01-preview'
            deployment_name = settings.AZURE_DEPLOYMENT_NAME if settings.AZURE_DEPLOYMENT_NAME else 'gpt-4o'
            
            # If still empty, the config might be using the new field names directly
            # Since settings uses AliasChoices, both should be available, but let's be safe
            if not azure_endpoint:
                # Try accessing via the validation alias
                azure_endpoint = getattr(settings, 'AZURE_OPENAI_ENDPOINT', '') or settings.AZURE_ENDPOINT
            if not api_key:
                api_key = getattr(settings, 'AZURE_OPENAI_API_KEY', '') or settings.OPENAI_API_KEY
            
            _validator_logger.info(f"📝 LLM Config - Endpoint: {azure_endpoint[:50] if azure_endpoint else 'None'}..., API Key: {'***' if api_key else 'None'}, Deployment: {deployment_name}")
            
            if not azure_endpoint or not api_key:
                raise ValueError(f"Missing Azure OpenAI config - Endpoint: {bool(azure_endpoint)}, API Key: {bool(api_key)}")
            
            self._llm = AzureChatOpenAI(
                azure_endpoint=azure_endpoint,
                api_key=api_key,
                api_version=api_version,
                deployment_name=deployment_name,
                temperature=0.0,
            )
            self._initialized = True
            _validator_logger.info("✅ LLM initialized successfully")
        except Exception as e:
            _validator_logger.error(f"❌ SQLValidator LLM initialization failed: {e}", exc_info=True)
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
        # CRITICAL: If error_message is provided (from SQL execution failure), ALWAYS attempt correction
        # This ensures validator handles all SQLMaker errors, even if schema validation passes
        if error_message:
            _validator_logger.info("=" * 80)
            _validator_logger.info("🔧 VALIDATOR: Error message provided - ALWAYS attempting correction")
            _validator_logger.info(f"Error message: {error_message[:500]}")
            _validator_logger.info(f"Original SQL: {sql_query}")
            _logger.info(f"Error message provided from execution failure. Will ALWAYS attempt correction: {error_message[:200]}")
            
            # Ensure LLM is initialized before attempting correction
            _validator_logger.info("📝 Ensuring LLM is initialized...")
            self._ensure_initialized()
            _validator_logger.info(f"📝 LLM initialized: {self._initialized}, LLM available: {self._llm is not None}")
            
            # Use the execution error message directly for correction
            if self._llm:
                _validator_logger.info("✅ LLM is available - proceeding with correction")
                _validator_logger.info("📝 Calling _correct_sql_with_llm()...")
                correction_result = self._correct_sql_with_llm(
                    sql_query=sql_query,
                    error_message=error_message,
                    original_question=original_question,
                    schema_info=schema_info
                )
                
                _validator_logger.info(f"📝 LLM correction returned:")
                _validator_logger.info(f"  - Has corrected_sql: {bool(correction_result.get('corrected_sql'))}")
                _validator_logger.info(f"  - Valid: {correction_result.get('valid')}")
                _validator_logger.info(f"  - Error: {correction_result.get('error')}")
                
                # If correction succeeded, validate it again
                if correction_result.get("corrected_sql"):
                    corrected_sql = correction_result["corrected_sql"]
                    _validator_logger.info(f"✅ LLM generated corrected SQL:")
                    _validator_logger.info(f"SQL: {corrected_sql}")
                    
                    _validator_logger.info("📝 Re-validating corrected SQL against schema...")
                    re_validation = self._validate_against_schema(corrected_sql)
                    _validator_logger.info(f"📝 Re-validation result: valid={re_validation.get('valid')}, error={re_validation.get('error')}")
                    
                    if re_validation["valid"]:
                        _validator_logger.info("✅ Validator corrected SQL and validation passed")
                        _logger.info("✅ Validator corrected SQL and validation passed")
                        return {
                            "valid": True,
                            "corrected_sql": corrected_sql,
                            "error": None,
                            "attempts": correction_result.get("attempts", 1)
                        }
                    else:
                        # Correction attempted but validation still fails - return it anyway for execution to try
                        _validator_logger.warning(f"⚠️ Corrected SQL still has validation errors: {re_validation.get('error')}, but returning for execution attempt")
                        _logger.warning(f"Corrected SQL still has validation errors: {re_validation.get('error')}, but returning for execution attempt")
                        return {
                            "valid": False,
                            "corrected_sql": corrected_sql,
                            "error": re_validation.get("error", "Correction attempted but validation still fails"),
                            "attempts": correction_result.get("attempts", 1)
                        }
                else:
                    _validator_logger.warning("⚠️ LLM correction did not return corrected SQL")
                    _logger.warning("LLM correction did not return corrected SQL")
                    return correction_result
            else:
                _validator_logger.error("❌ LLM not available for correction")
                _logger.warning("LLM not available for correction")
                return {
                    "valid": False,
                    "corrected_sql": None,
                    "error": "LLM not available for correction",
                    "attempts": 0
                }
        
        # If no error_message provided, do normal validation flow
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
        Validates SQL query against actual database schema by checking table and column names.
        Uses INFORMATION_SCHEMA to verify tables and columns exist.
        """
        try:
            # Extract table and column names from SQL
            tables = self._extract_tables(sql)
            columns_used = self._extract_columns(sql)
            
            if not tables:
                return {"valid": True, "error": None}  # Can't validate without tables
            
            # FIRST: Check if tables exist (this catches "Invalid object name" errors)
            invalid_tables = []
            for table in tables:
                if not self._table_exists(table):
                    invalid_tables.append(table)
            
            if invalid_tables:
                # Try to find similar table names
                suggestions = {}
                for invalid_table in invalid_tables:
                    similar = self._find_similar_tables(invalid_table, max_results=3)
                    if similar:
                        suggestions[invalid_table] = similar
                
                error_msg = f"Invalid table names: {', '.join(invalid_tables)}"
                if suggestions:
                    suggestion_text = "; ".join([f"{table} -> similar: {', '.join(sims)}" for table, sims in suggestions.items()])
                    error_msg += f" (Suggestions: {suggestion_text})"
                return {"valid": False, "error": error_msg}
            
            # SECOND: Check each column against actual schema
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
    
    def _table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database using INFORMATION_SCHEMA"""
        try:
            query = text("""
                SELECT COUNT(*) 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_SCHEMA = 'dbo' 
                  AND TABLE_NAME = :table_name
            """)
            result = self.db.execute(query, {
                "table_name": table_name
            }).scalar()
            
            return result > 0
        except Exception as e:
            _logger.warning(f"Error checking table {table_name}: {e}")
            # If we can't check, assume it exists (fail open)
            return True
    
    def _find_similar_tables(self, invalid_table: str, max_results: int = 5) -> list:
        """Find similar table names in the database using actual schema - completely generic"""
        try:
            # Get all tables from the database
            query = text("""
                SELECT TABLE_NAME
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA = 'dbo'
                  AND TABLE_TYPE = 'BASE TABLE'
                ORDER BY TABLE_NAME
            """)
            
            all_tables = self.db.execute(query).fetchall()
            
            if not all_tables:
                return []
            
            # Find similar tables using string matching
            invalid_upper = invalid_table.upper()
            similar = []
            
            for row in all_tables:
                table_name = row[0]
                table_upper = table_name.upper()
                
                # Check for similarity
                if invalid_upper in table_upper or table_upper in invalid_upper:
                    # Exact match or contains
                    priority = 1 if table_upper == invalid_upper else 2
                    similar.append((priority, table_name))
                elif self._table_name_similarity(invalid_upper, table_upper) > 0.4:
                    # Similar by edit distance (lower threshold for tables)
                    priority = 3
                    similar.append((priority, table_name))
                # Also check if keywords match (e.g., "loan" in both "Loans" and "super_loan_account_dim")
                elif self._has_common_keywords(invalid_upper, table_upper):
                    priority = 4
                    similar.append((priority, table_name))
            
            # Sort by priority and return top results
            similar.sort(key=lambda x: x[0])
            return [table for _, table in similar[:max_results]]
            
        except Exception as e:
            _logger.warning(f"Error finding similar tables for {invalid_table}: {e}")
            return []
    
    def _table_name_similarity(self, table1: str, table2: str) -> float:
        """Simple similarity check for table names - returns 0.0 to 1.0"""
        table1 = table1.upper()
        table2 = table2.upper()
        
        # Exact match
        if table1 == table2:
            return 1.0
        
        # One contains the other
        if table1 in table2 or table2 in table1:
            return 0.8
        
        # Check common substrings
        common_chars = set(table1) & set(table2)
        if len(common_chars) > len(table1) * 0.4:
            return 0.6
        
        return 0.0
    
    def _has_common_keywords(self, name1: str, name2: str) -> bool:
        """Check if two names share common keywords (e.g., 'loan', 'customer', 'account')"""
        # Normalize names for comparison
        name1_upper = name1.upper()
        name2_upper = name2.upper()
        
        # Extract potential keywords (words longer than 3 chars)
        # Split on both underscore and camelCase boundaries
        import re
        words1 = set([w for w in re.split(r'[_\s]+', name1_upper) if len(w) > 3])
        words2 = set([w for w in re.split(r'[_\s]+', name2_upper) if len(w) > 3])
        
        # Also check if name1 contains any significant word from name2 (or vice versa)
        # This helps match "LoanAccounts" with "super_loan_account_dim" (loan + account match)
        for word in words1:
            if len(word) > 3 and word in name2_upper:
                return True
        for word in words2:
            if len(word) > 3 and word in name1_upper:
                return True
        
        return len(words1 & words2) > 0
    
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
        _validator_logger.info("📝 Getting actual columns for tables from database...")
        actual_columns = self._get_actual_columns_for_tables(sql_query)
        _validator_logger.info(f"✅ Retrieved column info (length: {len(actual_columns) if actual_columns else 0})")
        
        # Also get list of all available tables for better context
        all_tables = []
        try:
            all_tables_query = text("""
                SELECT TABLE_NAME
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA = 'dbo'
                  AND TABLE_TYPE = 'BASE TABLE'
                ORDER BY TABLE_NAME
            """)
            all_tables_result = self.db.execute(all_tables_query).fetchall()
            all_tables = [row[0] for row in all_tables_result]
            _validator_logger.info(f"✅ Retrieved all available tables: {', '.join(all_tables)}")
            
            # If actual_columns is empty (table doesn't exist), find similar tables and get their columns
            if not actual_columns or len(actual_columns.strip()) == 0:
                _validator_logger.info("⚠️ No columns found for invalid table. Finding similar tables...")
                tables_in_sql = self._extract_tables(sql_query)
                for invalid_table in tables_in_sql:
                    if not self._table_exists(invalid_table):
                        similar_tables = self._find_similar_tables(invalid_table, max_results=2)
                        _validator_logger.info(f"📝 Found {len(similar_tables)} similar tables for '{invalid_table}': {similar_tables}")
                        
                        # Get columns from similar tables
                        similar_columns_info = []
                        for similar_table in similar_tables:
                            try:
                                query = text("""
                                    SELECT COLUMN_NAME, DATA_TYPE
                                    FROM INFORMATION_SCHEMA.COLUMNS
                                    WHERE TABLE_SCHEMA = 'dbo'
                                      AND TABLE_NAME = :table_name
                                    ORDER BY ORDINAL_POSITION
                                """)
                                results = self.db.execute(query, {"table_name": similar_table}).fetchall()
                                if results:
                                    cols = [f"{similar_table}.{row[0]} ({row[1]})" for row in results]
                                    similar_columns_info.append(f"{similar_table} (similar to '{invalid_table}'):\n  " + "\n  ".join(cols))
                                    _validator_logger.info(f"✅ Got {len(cols)} columns from {similar_table}")
                            except Exception as e:
                                _validator_logger.warning(f"⚠️ Error getting columns for {similar_table}: {e}")
                        
                        if similar_columns_info:
                            actual_columns = "\n\n".join(similar_columns_info)
                            _validator_logger.info(f"✅ Generated column info from similar tables (length: {len(actual_columns)})")
            
            # Add tables list to actual_columns info
            if all_tables:
                tables_list = f"Available tables in database:\n{', '.join(all_tables)}\n\n"
                actual_columns = tables_list + (actual_columns if actual_columns else "")
        except Exception as e:
            _validator_logger.warning(f"⚠️ Could not get all tables list: {e}")
        
        system_prompt = (
            "You are a SQL correction specialist. Your job is to fix SQL queries that have invalid table or column names.\n"
            "CRITICAL RULES - YOU MUST FOLLOW THESE EXACTLY:\n"
            "1. Use ONLY the exact column names provided in the 'ACTUAL TABLE AND COLUMN NAMES IN DATABASE' section\n"
            "2. Do NOT invent, guess, or create column names (e.g., do NOT use 'loan_id', 'customer_id', 'loan_end_date', 'loan_status')\n"
            "3. Do NOT convert column names to snake_case or camelCase - use the EXACT names as shown (they may be UPPERCASE, lowercase, or mixed)\n"
            "4. If a table doesn't exist, find the most similar table from the actual schema (e.g., 'Loans' -> 'super_loan_account_dim' or 'caselite_loan_applications')\n"
            "5. When replacing a table, you MUST also replace ALL column names with the actual column names from the new table\n"
            "6. Match columns based on:\n"
            "   - Exact name match if possible\n"
            "   - Semantic meaning (e.g., 'LoanEndDate' -> find date columns in the new table)\n"
            "   - Data type (e.g., dates, amounts, IDs)\n"
            "7. Return ONLY the corrected SQL query (no markdown, no explanations, no code blocks)\n"
            "8. Preserve the original query logic and structure\n"
            "9. Use TOP (not LIMIT) for SQL Server\n"
            "10. If you cannot find a matching column, remove that column from SELECT or WHERE clause rather than inventing a name\n"
        )
        
        user_prompt_parts = [
            f"Original question: {original_question}\n\n",
            f"SQL query with error:\n{sql_query}\n\n",
            f"Error message:\n{error_message}\n\n"
        ]
        
        if actual_columns:
            _validator_logger.info(f"📝 Adding actual columns info to prompt (length: {len(actual_columns)})")
            user_prompt_parts.append(f"ACTUAL TABLE AND COLUMN NAMES IN DATABASE:\n{actual_columns}\n\n")
            user_prompt_parts.append(
                "CRITICAL: You MUST use ONLY the exact column names listed above. "
                "Do NOT invent column names or use generic names like 'loan_id', 'customer_id', 'loan_end_date', etc. "
                "Use the EXACT column names as they appear in the database schema above (case-sensitive).\n\n"
            )
        
        if schema_info:
            user_prompt_parts.append(f"Schema information:\n{schema_info[:2000]}\n\n")
        
        # Check if error is about table or column
        is_table_error = "Invalid object name" in error_message or "42S02" in error_message
        is_column_error = "Invalid column name" in error_message or "42S22" in error_message
        
        if is_table_error:
            user_prompt_parts.append(
                "CRITICAL: The error is about an INVALID TABLE NAME.\n"
                "You MUST:\n"
                "- Replace the invalid table name with the correct table name from the schema\n"
                "- Use the 'ACTUAL TABLE AND COLUMN NAMES IN DATABASE' section above to find the correct table names.\n"
                "- Match tables based on:\n"
                "  * Name similarity (find tables with similar names from the actual schema)\n"
                "  * Context from the original question (e.g., 'loans' -> loan-related tables)\n"
                "  * Column names used in the query (match columns to the correct table)\n"
                "- Update ALL references to the invalid table (FROM, JOIN, aliases, column prefixes)\n"
                "- CRITICAL: When replacing columns, use ONLY the exact column names from the 'ACTUAL TABLE AND COLUMN NAMES IN DATABASE' section above\n"
                "- Do NOT invent column names - if the original query has an invalid column name, find the closest matching column from the actual schema provided above\n"
                "- Do NOT use generic names like 'loan_id', 'customer_id', 'loan_end_date' - use the EXACT names from the schema\n"
                "- Preserve the original query intent while using correct table and column names\n\n"
            )
        
        if is_column_error:
            user_prompt_parts.append(
                "CRITICAL: The error is about an INVALID COLUMN NAME.\n"
                "You MUST:\n"
                "- Replace the invalid column name with the correct column name from the schema\n"
                "- Use ONLY the actual column names from the schema provided above\n"
                "- Match columns based on:\n"
                "  * Name similarity (e.g., 'invalid_col' might be 'valid_col' or 'similar_col')\n"
                "  * Context (e.g., if looking for status, find status-related columns)\n"
                "  * Data type (e.g., if filtering by date, use date columns)\n"
                "- Preserve the original query intent while using correct column names\n"
                "- If a column doesn't exist and no similar column is found, remove that condition or use a different approach\n\n"
            )
        
        user_prompt_parts.append(
            "Return ONLY the corrected SQL query (no markdown, no explanations):"
        )
        
        user_prompt = "".join(user_prompt_parts)
        
        try:
            from langchain_core.messages import SystemMessage, HumanMessage
            
            # Log the actual columns info being sent to LLM (for debugging)
            if actual_columns:
                _validator_logger.info(f"📝 Actual columns info being sent to LLM (first 1000 chars): {actual_columns[:1000]}")
            else:
                _validator_logger.warning("⚠️ No actual columns info available for LLM - this may cause incorrect column names")
            
            _validator_logger.info("📝 Invoking LLM for SQL correction...")
            resp = self._llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ])
            
            _validator_logger.info("✅ LLM response received")
            corrected_sql = resp.content if hasattr(resp, "content") else str(resp)
            _validator_logger.info(f"📝 Raw LLM response (first 500 chars): {corrected_sql[:500]}")
            
            corrected_sql = self._clean_sql(corrected_sql)
            _validator_logger.info(f"📝 Cleaned SQL: {corrected_sql}")
            
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

