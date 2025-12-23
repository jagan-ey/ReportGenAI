"""
LangChain SQL Agent for natural language to SQL conversion
Simplified version without vector DB - uses direct schema information
Uses Azure OpenAI
"""
from typing import Optional, Dict, Any
from app.core.config import settings
import json
import logging
import os
from datetime import datetime

# Setup dedicated logger for SQL agent debugging
_log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')
os.makedirs(_log_dir, exist_ok=True)

_sql_agent_logger = logging.getLogger('sql_agent_debug')
_sql_agent_logger.setLevel(logging.DEBUG)

# Remove existing handlers to avoid duplicates
_sql_agent_logger.handlers.clear()

# Create file handler for SQL agent debug logs
_log_file = os.path.join(_log_dir, f'sql_agent_debug_{datetime.now().strftime("%Y%m%d")}.log')
_file_handler = logging.FileHandler(_log_file, mode='a', encoding='utf-8')
_file_handler.setLevel(logging.DEBUG)

# Create formatter
_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
_file_handler.setFormatter(_formatter)

# Add handler to logger
_sql_agent_logger.addHandler(_file_handler)

# Also add console handler if DEBUG mode
if settings.DEBUG:
    _console_handler = logging.StreamHandler()
    _console_handler.setLevel(logging.DEBUG)
    _console_handler.setFormatter(_formatter)
    _sql_agent_logger.addHandler(_console_handler)

# Lazy imports to avoid startup errors
def _import_langchain():
    """Lazy import langchain modules with workaround for version conflicts"""
    try:
        # Workaround: Patch the problematic import before importing langchain
        import sys
        from unittest.mock import MagicMock
        
        # Create a mock for the problematic module if it doesn't exist
        if 'langchain_community.graphs.memgraph_graph' not in sys.modules:
            mock_module = MagicMock()
            mock_module.RAW_SCHEMA_QUERY = "SELECT * FROM schema"
            sys.modules['langchain_community.graphs.memgraph_graph'] = mock_module
        
        from langchain.agents import create_sql_agent
        from langchain.agents.agent_toolkits import SQLDatabaseToolkit
        from langchain.sql_database import SQLDatabase
        from langchain_openai import AzureChatOpenAI
        from langchain.agents.agent_types import AgentType
        return create_sql_agent, SQLDatabaseToolkit, SQLDatabase, AzureChatOpenAI, AgentType
    except ImportError as e:
        # If the workaround doesn't work, try new imports
        try:
            from langchain_community.agent_toolkits.sql.base import create_sql_agent
            from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
            from langchain_community.utilities import SQLDatabase
            from langchain_openai import AzureChatOpenAI
            from langchain.agents.agent_types import AgentType
            return create_sql_agent, SQLDatabaseToolkit, SQLDatabase, AzureChatOpenAI, AgentType
        except ImportError:
            # Final fallback to old imports
            from langchain.agents import create_sql_agent
            from langchain.agents.agent_toolkits import SQLDatabaseToolkit
            from langchain.sql_database import SQLDatabase
            from langchain_openai import AzureChatOpenAI
            from langchain.agents.agent_types import AgentType
            return create_sql_agent, SQLDatabaseToolkit, SQLDatabase, AzureChatOpenAI, AgentType


class SQLAgentService:
    """Service for handling SQL generation from natural language"""
    
    def __init__(self, db_url: str):
        self.db_url = db_url
        self._db = None
        self._llm = None
        self._toolkit = None
        self._agent = None
        self._initialized = False
        self._sql_callback = None  # Callback to capture SQL
        self._schema_cache = None  # Cache table info for performance
    
    def _ensure_initialized(self):
        """Lazy initialization of langchain components"""
        if self._initialized:
            return
        
        try:
            # Import langchain modules
            create_sql_agent, SQLDatabaseToolkit, SQLDatabase, AzureChatOpenAI, AgentType = _import_langchain()
            
            # Initialize database connection
            # Get allowed tables from config or use all tables
            allowed_tables = None
            if settings.SQL_AGENT_ALLOWED_TABLES:
                # Parse comma-separated list from config
                allowed_tables = [t.strip() for t in settings.SQL_AGENT_ALLOWED_TABLES.split(",") if t.strip()]
                _sql_agent_logger.info(f"SQL Agent restricted to {len(allowed_tables)} tables from config")
            else:
                # No restriction - allow all tables (generic)
                _sql_agent_logger.info("SQL Agent allowed to access all tables (no restriction)")
            
            # Use include_tables only if specified, otherwise allow all tables
            db_kwargs = {
                "uri": self.db_url,
                "sample_rows_in_table_info": 3  # Include sample rows for better context
            }
            if allowed_tables:
                db_kwargs["include_tables"] = allowed_tables
            
            self._db = SQLDatabase.from_uri(**db_kwargs)

            # Ensure any SQL executed through LangChain tools is cleaned (strip ```sql fences)
            # This prevents SQL Server errors like "Incorrect syntax near '`'" when models wrap SQL in markdown.
            try:
                if hasattr(self._db, "run") and callable(getattr(self._db, "run")):
                    _orig_run = self._db.run

                    def _run_clean(query: str, *args, **kwargs):
                        return _orig_run(self._clean_sql_string(query), *args, **kwargs)

                    self._db.run = _run_clean  # type: ignore[attr-defined]

                if hasattr(self._db, "run_no_throw") and callable(getattr(self._db, "run_no_throw")):
                    _orig_run_no_throw = self._db.run_no_throw

                    def _run_no_throw_clean(query: str, *args, **kwargs):
                        return _orig_run_no_throw(self._clean_sql_string(query), *args, **kwargs)

                    self._db.run_no_throw = _run_no_throw_clean  # type: ignore[attr-defined]
            except Exception as e:
                _sql_agent_logger.debug(f"Could not patch SQLDatabase.run cleaners: {e}")
            
            if allowed_tables:
                _sql_agent_logger.info(f"✅ SQL Database initialized with restricted access to {len(allowed_tables)} tables: {', '.join(allowed_tables)}")
            else:
                _sql_agent_logger.info("✅ SQL Database initialized with access to all tables")
            
            # Use Azure OpenAI - with better error handling
            try:
                self._llm = AzureChatOpenAI(
                    azure_endpoint=settings.AZURE_ENDPOINT,
                    api_key=settings.OPENAI_API_KEY,
                    api_version=settings.AZURE_API_VERSION,
                    deployment_name=settings.AZURE_DEPLOYMENT_NAME,
                    temperature=settings.LLM_TEMPERATURE
                )
            except Exception as e:
                raise Exception(
                    f"Failed to initialize Azure OpenAI. Please check:\n"
                    f"1. Azure endpoint: {settings.AZURE_ENDPOINT}\n"
                    f"2. API key is set\n"
                    f"3. Deployment name: {settings.AZURE_DEPLOYMENT_NAME}\n"
                    f"Error: {str(e)}"
                )
            
            self._toolkit = SQLDatabaseToolkit(db=self._db, llm=self._llm)
            
            # Create a callback to capture SQL queries during execution
            from langchain_core.callbacks import BaseCallbackHandler
            from typing import Any, Dict, List
            
            class SQLCaptureCallback(BaseCallbackHandler):
                """Callback to capture SQL queries from agent execution"""
                def __init__(self):
                    self.captured_sql = None
                    self.tool_inputs = []
                
                def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs) -> None:
                    """Capture tool inputs, especially SQL queries"""
                    tool_name = serialized.get("name", "")
                    input_str_val = str(input_str) if input_str else ""
                    _sql_agent_logger.debug(f"🔍 Callback: Tool started - name={tool_name}, input={input_str_val[:200]}")
                    
                    # Check if input_str itself looks like SQL (regardless of tool name)
                    input_str_upper = input_str_val.upper()
                    if "SELECT" in input_str_upper and "FROM" in input_str_upper and len(input_str_val) > 20:
                        # This looks like SQL - capture it (clean it first)
                        potential_sql = self._clean_sql(input_str_val)
                        if not self.captured_sql:  # Only if we haven't captured one yet
                            self.captured_sql = potential_sql
                            _sql_agent_logger.info(f"✅ Captured SQL via callback (on_tool_start): {self.captured_sql[:200]}...")
                    
                    # Also check if this is a SQL query tool (multiple possible names)
                    if any(keyword in tool_name.lower() for keyword in ["sql_db_query", "query", "sql"]):
                        # This is likely a SQL query tool - input_str is the SQL
                        if "SELECT" in input_str_upper:
                            if not self.captured_sql:  # Only if we haven't captured one yet
                                self.captured_sql = self._clean_sql(input_str_val)
                                _sql_agent_logger.info(f"✅ Captured SQL via callback (sql_db_query tool): {self.captured_sql[:200]}...")
                    
                    self.tool_inputs.append({"tool": tool_name, "input": input_str_val[:500]})
                
                def _clean_sql(self, sql: str) -> str:
                    """Remove markdown code blocks and clean SQL"""
                    import re
                    # Remove ```sql and ``` markers
                    sql = re.sub(r'^```sql\s*', '', sql, flags=re.IGNORECASE | re.MULTILINE)
                    sql = re.sub(r'^```\s*', '', sql, flags=re.IGNORECASE | re.MULTILINE)
                    sql = re.sub(r'```\s*$', '', sql, flags=re.IGNORECASE | re.MULTILINE)
                    sql = sql.strip().rstrip(';').strip()
                    return sql
                
                def on_tool_end(self, output: str, **kwargs) -> None:
                    """Log when tool ends"""
                    _sql_agent_logger.debug(f"🔍 Callback: Tool ended, output length={len(str(output))}")
                
                def on_chain_start(self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs) -> None:
                    """Log chain starts"""
                    try:
                        if serialized is None:
                            chain_name = "unknown"
                        else:
                            name = serialized.get("name") if serialized else None
                            chain_id = serialized.get("id") if serialized else None
                            if name:
                                chain_name = name
                            elif chain_id:
                                if isinstance(chain_id, list) and len(chain_id) > 0:
                                    chain_name = chain_id[-1]
                                else:
                                    chain_name = str(chain_id)
                            else:
                                chain_name = "unknown"
                        _sql_agent_logger.debug(f"🔍 Callback: Chain started - {chain_name}")
                    except Exception as e:
                        # Silently handle errors in callback to avoid breaking the agent
                        _sql_agent_logger.debug(f"🔍 Callback: Chain started - (error getting name: {str(e)})")
                
                def on_agent_action(self, action, **kwargs) -> None:
                    """Capture agent actions - this is where SQL queries are often found"""
                    _sql_agent_logger.debug(f"🔍 Callback: Agent action - {type(action)}")
                    if hasattr(action, 'tool'):
                        tool_name = getattr(action.tool, 'name', '') if hasattr(action.tool, 'name') else str(action.tool)
                        tool_input = getattr(action, 'tool_input', '') if hasattr(action, 'tool_input') else ''
                        _sql_agent_logger.debug(f"🔍 Callback: Agent action tool={tool_name}, input={str(tool_input)[:200]}")
                        
                        # Check if this is SQL
                        if "SELECT" in str(tool_input).upper() and "FROM" in str(tool_input).upper():
                            # Clean SQL: remove markdown code blocks
                            cleaned_sql = self._clean_sql(str(tool_input))
                            self.captured_sql = cleaned_sql
                            _sql_agent_logger.info(f"✅ Captured SQL via agent_action callback: {self.captured_sql[:200]}...")
                
                def _clean_sql(self, sql: str) -> str:
                    """Remove markdown code blocks and clean SQL"""
                    import re
                    # Remove ```sql and ``` markers
                    sql = re.sub(r'^```sql\s*', '', sql, flags=re.IGNORECASE | re.MULTILINE)
                    sql = re.sub(r'^```\s*', '', sql, flags=re.IGNORECASE | re.MULTILINE)
                    sql = re.sub(r'```\s*$', '', sql, flags=re.IGNORECASE | re.MULTILINE)
                    sql = sql.strip().rstrip(';').strip()
                    return sql
            
            # Initialize callback
            sql_callback = SQLCaptureCallback()
            
            # Initialize the SQL agent with optimized settings
            # Note: max_execution_time and early_stopping_method may not be available in all versions
            try:
                self._agent = create_sql_agent(
                    llm=self._llm,
                    toolkit=self._toolkit,
                    verbose=settings.DEBUG,
                    agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
                    handle_parsing_errors=True,
                    max_iterations=15,  # Increased from 5 to allow more complex queries
                    max_execution_time=60,  # 60 second timeout
                    callbacks=[sql_callback]  # Add callback to capture SQL
                )
                self._sql_callback = sql_callback  # Store callback for later access
            except TypeError:
                # If max_execution_time is not supported, use without it
                self._agent = create_sql_agent(
                    llm=self._llm,
                    toolkit=self._toolkit,
                    verbose=settings.DEBUG,
                    agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
                    handle_parsing_errors=True,
                    max_iterations=15,  # Increased from 5 to allow more complex queries
                    callbacks=[sql_callback]  # Add callback to capture SQL
                )
                self._sql_callback = sql_callback  # Store callback for later access
            
            self._initialized = True
        except ImportError as e:
            raise ImportError(
                f"Failed to import LangChain modules. Please ensure all dependencies are installed: {e}\n"
                "Try: pip install -r requirements.txt"
            )
        except Exception as e:
            # Re-raise with better context
            raise Exception(f"Failed to initialize SQL Agent: {str(e)}")
    
    @property
    def db(self):
        """Get database connection"""
        self._ensure_initialized()
        return self._db
    
    @property
    def agent(self):
        """Get SQL agent"""
        self._ensure_initialized()
        return self._agent
    
    def get_schema_info(self) -> str:
        """Get database schema information as string"""
        if self._schema_cache:
            return self._schema_cache
        self._schema_cache = self.db.get_table_info()
        return self._schema_cache
    
    def execute_query(self, question: str) -> Dict[str, Any]:
        """
        Execute a natural language query and return results
        
        Args:
            question: Natural language question
            
        Returns:
            Dictionary with query results and metadata
        """
        try:
            # Ensure agent is initialized
            self._ensure_initialized()
            
            # Reset callback before execution
            if hasattr(self, '_sql_callback') and self._sql_callback:
                self._sql_callback.captured_sql = None
                self._sql_callback.tool_inputs = []
                _sql_agent_logger.debug("Callback reset before execution")
            else:
                _sql_agent_logger.warning("No callback available!")
            
            # Run the agent with callback
            try:
                # Invoke with callback explicitly
                if hasattr(self, '_sql_callback') and self._sql_callback:
                    result = self.agent.invoke({"input": question}, config={"callbacks": [self._sql_callback]})
                else:
                    result = self.agent.invoke({"input": question})
                
                # Check if callback captured SQL immediately after execution
                if hasattr(self, '_sql_callback') and self._sql_callback:
                    _sql_agent_logger.debug(f"After execution - callback captured_sql: {self._sql_callback.captured_sql}")
                    _sql_agent_logger.debug(f"After execution - callback tool_inputs: {len(self._sql_callback.tool_inputs)}")
                    if self._sql_callback.captured_sql:
                        _sql_agent_logger.info(f"✅ SQL captured via callback: {self._sql_callback.captured_sql[:200]}...")
                
                # Debug: Log full result structure to file
                _sql_agent_logger.debug(f"=== SQL Extraction Debug for question: {question[:100]} ===")
                _sql_agent_logger.debug(f"Result type: {type(result)}")
                
                if isinstance(result, dict):
                    _sql_agent_logger.debug(f"Result keys: {list(result.keys())}")
                    # Log each key's value type and preview
                    for key in result.keys():
                        value = result[key]
                        if isinstance(value, (list, tuple)):
                            _sql_agent_logger.debug(f"  {key}: {type(value)} with {len(value)} items")
                            if len(value) > 0:
                                _sql_agent_logger.debug(f"    First item type: {type(value[0])}")
                        elif isinstance(value, str):
                            _sql_agent_logger.debug(f"  {key}: {type(value)} = {value[:200]}")
                        else:
                            _sql_agent_logger.debug(f"  {key}: {type(value)} = {str(value)[:200]}")
                    
                    intermediate_steps = result.get("intermediate_steps", [])
                    _sql_agent_logger.debug(f"Found {len(intermediate_steps)} intermediate steps")
                    
                    if intermediate_steps:
                        for i, step in enumerate(reversed(intermediate_steps)):
                            if isinstance(step, (list, tuple)) and len(step) > 0:
                                step_action = step[0]
                                _sql_agent_logger.debug(f"Step {i}: step_action type={type(step_action)}")
                                if hasattr(step_action, 'tool_input'):
                                    tool_input = step_action.tool_input
                                    tool_name = getattr(step_action, 'tool', None)
                                    tool_name_str = getattr(tool_name, 'name', None) if tool_name else None
                                    _sql_agent_logger.debug(f"Step {i}: tool_name={tool_name_str}, tool_input type={type(tool_input)}, tool_input={str(tool_input)[:300]}")
                                if hasattr(step_action, 'tool'):
                                    tool_obj = step_action.tool
                                    _sql_agent_logger.debug(f"Step {i}: tool object={tool_obj}, tool type={type(tool_obj)}")
                                    if hasattr(tool_obj, 'name'):
                                        _sql_agent_logger.debug(f"Step {i}: tool.name={tool_obj.name}")
                elif hasattr(result, '__dict__'):
                    _sql_agent_logger.debug(f"Result is object with attributes: {list(result.__dict__.keys())}")
                    for attr in result.__dict__.keys():
                        value = getattr(result, attr)
                        _sql_agent_logger.debug(f"  {attr}: {type(value)}")
                else:
                    _sql_agent_logger.warning(f"Result is unexpected type: {type(result)}, value: {str(result)[:500]}")
            except Exception as agent_error:
                error_str = str(agent_error)
                # Check if it's an iteration/timeout error
                if "iteration limit" in error_str.lower() or "time limit" in error_str.lower() or "Agent stopped" in error_str:
                    return {
                        "success": False,
                        "error": (
                            "Query processing exceeded time or iteration limits. "
                            "This might happen with complex questions. "
                            "Try: 1) Breaking the question into simpler parts, "
                            "2) Using more specific table/column names, "
                            "3) Using a predefined query for guaranteed results."
                        ),
                        "answer": None,
                        "sql_query": None
                    }
                raise
            
            # Extract SQL query from result - improved extraction logic
            sql_query = None
            answer_text = ""
            
            # Method 1: Check if result is a dict with output
            if isinstance(result, dict):
                answer_text = result.get("output", "") or result.get("answer", "")
                
                # Check intermediate_steps for SQL - iterate in reverse to get most recent SQL first
                intermediate_steps = result.get("intermediate_steps", [])
                
                for step_idx, step in enumerate(reversed(intermediate_steps)):
                    if isinstance(step, (list, tuple)) and len(step) >= 2:
                        step_action = step[0]
                        step_observation = step[1] if len(step) > 1 else None
                        
                        # Check action for tool_input (this is where SQL queries are usually stored)
                        if step_action:
                            tool_input = None
                            tool_name = None
                            
                            # Try different ways to access tool_input and tool name
                            # Method 1: Direct attribute access
                            if hasattr(step_action, 'tool_input'):
                                tool_input = step_action.tool_input
                            if hasattr(step_action, 'tool'):
                                tool_obj = step_action.tool
                                if hasattr(tool_obj, 'input'):
                                    tool_input = tool_obj.input
                                if hasattr(tool_obj, 'name'):
                                    tool_name = str(tool_obj.name)
                            
                            # Method 2: Dict access
                            if not tool_input and isinstance(step_action, dict):
                                tool_input = step_action.get('tool_input') or step_action.get('input')
                                tool_name = step_action.get('tool') or step_action.get('tool_name')
                            
                            # Method 3: Check if step_action itself is a string (sometimes it is)
                            if not tool_input and isinstance(step_action, str):
                                    if 'SELECT' in step_action.upper():
                                        potential_sql = step_action.strip()
                                        if self.validate_sql(potential_sql):
                                            sql_query = potential_sql
                                            _sql_agent_logger.info(f"✅ Extracted SQL from step_action string: {sql_query[:200]}...")
                                            break
                            
                            # Extract SQL from tool_input - AGGRESSIVE EXTRACTION
                            if tool_input:
                                tool_str = str(tool_input)
                                
                                _sql_agent_logger.debug(f"Step {step_idx}: tool_name={tool_name}, tool_input type={type(tool_input)}, tool_input={tool_str[:300]}")
                                
                                # CRITICAL: For sql_db_query, tool_input IS the SQL query directly
                                # Check if this looks like SQL (contains SELECT and FROM)
                                if 'SELECT' in tool_str.upper() and 'FROM' in tool_str.upper():
                                    # This is likely SQL - extract it directly
                                    potential_sql = tool_str.strip().strip('"').strip("'")
                                    # Remove trailing semicolon if present
                                    potential_sql = potential_sql.rstrip(';').strip()
                                    
                                    # Validate it's actually SQL
                                    if self.validate_sql(potential_sql):
                                        sql_query = potential_sql
                                        _sql_agent_logger.info(f"✅ Extracted SQL from tool_input (direct): {sql_query[:200]}...")
                                        break
                                
                                # Also check for SQL in any tool_input (fallback with cleanup)
                                # Clean up common prefixes/suffixes
                                if tool_str.startswith("sql_query="):
                                    tool_str = tool_str[10:].strip('"\'')
                                elif tool_str.startswith("query="):
                                    tool_str = tool_str[6:].strip('"\'')
                                
                                # Validate and extract SQL
                                if 'SELECT' in tool_str.upper():
                                    # Try to extract just the SQL part
                                    import re
                                    # Remove markdown code blocks
                                    tool_str = re.sub(r'```sql\s*', '', tool_str, flags=re.IGNORECASE)
                                    tool_str = re.sub(r'```\s*', '', tool_str)
                                    
                                    sql_match = re.search(r'(SELECT[\s\S]*?)(?:\n\n|$|;|```)', tool_str, re.IGNORECASE | re.MULTILINE)
                                    if sql_match:
                                        potential_sql = sql_match.group(1).strip()
                                    else:
                                        potential_sql = tool_str.strip()
                                    
                                    # Remove trailing semicolon
                                    potential_sql = potential_sql.rstrip(';').strip()
                                    
                                    if self.validate_sql(potential_sql):
                                        sql_query = potential_sql
                                        _sql_agent_logger.info(f"✅ Extracted SQL from tool_input (fallback): {sql_query[:200]}...")
                                        break
                        
                        # Check observation for SQL (sometimes SQL appears in observations)
                        if not sql_query and step_observation:
                            obs_str = str(step_observation)
                            if 'SELECT' in obs_str.upper():
                                import re
                                # Try multiple patterns to extract SQL
                                sql_patterns = [
                                    r'```sql\s*(SELECT[\s\S]*?)```',  # SQL in code blocks
                                    r'(SELECT[\s\S]*?)(?:\n\n|$|;)',  # SQL until double newline or semicolon
                                ]
                                for pattern in sql_patterns:
                                    sql_match = re.search(pattern, obs_str, re.IGNORECASE | re.MULTILINE)
                                    if sql_match:
                                        potential_sql = sql_match.group(1) if sql_match.lastindex else sql_match.group(0)
                                        potential_sql = potential_sql.strip().strip('```sql').strip('```').strip()
                                        if self.validate_sql(potential_sql):
                                            sql_query = potential_sql
                                            break
                                if sql_query:
                                    break
            
            # Method 2: Check if answer_text contains SQL (sometimes agent returns SQL in final answer)
            if not sql_query and answer_text:
                import re
                # Look for SQL queries in the answer text with multiple patterns
                sql_patterns = [
                    r'```sql\s*(SELECT[\s\S]*?)```',  # SQL in code blocks
                    r'SELECT[\s\S]*?;',  # SQL ending with semicolon
                    r'SELECT[\s\S]*?(?=\n\n|\Z)',  # SQL until double newline or end
                ]
                for pattern in sql_patterns:
                    matches = re.finditer(pattern, answer_text, re.IGNORECASE | re.MULTILINE)
                    for match in matches:
                        potential_sql = match.group(1) if match.lastindex else match.group(0)
                        potential_sql = potential_sql.strip().strip('```sql').strip('```').strip()
                        if self.validate_sql(potential_sql):
                            sql_query = potential_sql
                            break
                    if sql_query:
                        break
            
            # Check callback for captured SQL (CRITICAL FALLBACK - since intermediate_steps is empty)
            if not sql_query:
                if hasattr(self, '_sql_callback') and self._sql_callback:
                    _sql_agent_logger.debug(f"Checking callback - captured_sql: {self._sql_callback.captured_sql}")
                    _sql_agent_logger.debug(f"Callback tool_inputs count: {len(self._sql_callback.tool_inputs)}")
                    
                    # First check if we directly captured SQL
                    if self._sql_callback.captured_sql:
                        # Clean SQL: remove markdown code blocks if present
                        sql_query = self._clean_sql_string(self._sql_callback.captured_sql)
                        _sql_agent_logger.info(f"✅ Using SQL from callback (direct capture): {sql_query[:200]}...")
                    else:
                        # Check all tool inputs for SQL
                        _sql_agent_logger.debug("Checking all callback tool_inputs for SQL...")
                        for i, ti in enumerate(self._sql_callback.tool_inputs):
                            tool_name = ti.get('tool', 'unknown')
                            tool_input = str(ti.get('input', ''))
                            _sql_agent_logger.debug(f"  Tool input {i}: tool={tool_name}, input={tool_input[:200]}")
                            
                            if "SELECT" in tool_input.upper() and "FROM" in tool_input.upper():
                                potential_sql = self._clean_sql_string(tool_input)
                                if self.validate_sql(potential_sql):
                                    sql_query = potential_sql
                                    _sql_agent_logger.info(f"✅ Extracted SQL from callback tool_inputs[{i}]: {sql_query[:200]}...")
                                    break
                else:
                    _sql_agent_logger.warning("No callback available to check for SQL!")
            
            # If we have SQL but no answer text, create a basic answer
            if sql_query and not answer_text:
                answer_text = "Generated SQL query for your question."
            
            # IMPORTANT: Only return success=True if we have SQL query
            # If no SQL was extracted, log detailed debug info
            if not sql_query:
                _sql_agent_logger.warning(f"❌ SQL extraction FAILED. Answer text: {answer_text[:200]}")
                if isinstance(result, dict):
                    intermediate_steps = result.get("intermediate_steps", [])
                    _sql_agent_logger.warning(f"Intermediate steps count: {len(intermediate_steps)}")
                    if intermediate_steps:
                        # Log first step details
                        first_step = intermediate_steps[-1]  # Most recent
                        if isinstance(first_step, (list, tuple)) and len(first_step) > 0:
                            first_action = first_step[0]
                            _sql_agent_logger.warning(f"First step action type: {type(first_action)}")
                            if hasattr(first_action, 'tool_input'):
                                _sql_agent_logger.warning(f"First step tool_input: {str(first_action.tool_input)[:300]}")
                            if hasattr(first_action, 'tool'):
                                _sql_agent_logger.warning(f"First step tool: {first_action.tool}")
                                if hasattr(first_action.tool, 'name'):
                                    _sql_agent_logger.warning(f"First step tool.name: {first_action.tool.name}")
                _sql_agent_logger.debug("=" * 80)
            else:
                _sql_agent_logger.info(f"✅ SQL extraction SUCCESS. SQL: {sql_query[:200]}...")
                _sql_agent_logger.debug("=" * 80)
            
            return {
                "success": sql_query is not None,  # Only success if SQL was extracted
                "answer": answer_text if sql_query else "Unable to extract SQL query from agent response.",
                "sql_query": sql_query,  # This will be None if extraction failed
                "raw_result": result if settings.DEBUG else None  # Only include raw result in debug mode
            }
        except ImportError as e:
            return {
                "success": False,
                "error": f"LangChain modules not available: {str(e)}. Please install dependencies.",
                "answer": None,
                "sql_query": None
            }
        except Exception as e:
            error_msg = str(e)
            import traceback
            
            # Provide more helpful error messages
            if "iteration limit" in error_msg.lower() or "time limit" in error_msg.lower():
                error_msg = (
                    "Query processing exceeded time or iteration limits. "
                    "This might happen with complex questions. "
                    "Try: 1) Breaking the question into simpler parts, "
                    "2) Using more specific table/column names, "
                    "3) Using a predefined query for guaranteed results."
                )
            elif "api key" in error_msg.lower() or "authentication" in error_msg.lower():
                error_msg = f"Azure OpenAI authentication failed: {error_msg}. Please check your API key."
            elif "deployment" in error_msg.lower() or "not found" in error_msg.lower():
                error_msg = f"Deployment not found: {error_msg}. Please check deployment name: {settings.AZURE_DEPLOYMENT_NAME}"
            elif "endpoint" in error_msg.lower() or "connection" in error_msg.lower():
                error_msg = f"Connection error: {error_msg}. Please check Azure endpoint: {settings.AZURE_ENDPOINT}"
            elif "Agent stopped" in error_msg:
                error_msg = (
                    "The AI agent stopped processing your query. "
                    "This can happen with very complex questions. "
                    "Please try: 1) Simplifying your question, "
                    "2) Being more specific about tables/columns, "
                    "3) Using a predefined query instead."
                )
            
            # Log full error to file
            _sql_agent_logger.error(f"SQL Agent Error: {error_msg}")
            _sql_agent_logger.error(f"Full traceback: {traceback.format_exc()}")
            _sql_agent_logger.debug("=" * 80)
            
            return {
                "success": False,
                "error": error_msg,
                "answer": None,
                "sql_query": None
            }
    
    def _clean_sql_string(self, sql: str) -> str:
        """Remove markdown code blocks and clean SQL"""
        import re
        if not sql:
            return ""
        # Remove ```sql and ``` markers
        sql = re.sub(r'^```sql\s*', '', sql, flags=re.IGNORECASE | re.MULTILINE)
        sql = re.sub(r'^```\s*', '', sql, flags=re.IGNORECASE | re.MULTILINE)
        sql = re.sub(r'```\s*$', '', sql, flags=re.IGNORECASE | re.MULTILINE)
        sql = sql.strip().rstrip(';').strip()
        return sql
    
    def validate_sql(self, sql: str) -> bool:
        """Basic SQL validation"""
        if not sql:
            return False
        # Clean SQL first (remove markdown code blocks)
        sql = self._clean_sql_string(sql)
        sql_upper = sql.upper().strip()
        # Prevent dangerous operations
        dangerous_keywords = ['DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'CREATE', 'INSERT', 'UPDATE']
        for keyword in dangerous_keywords:
            if keyword in sql_upper:
                return False
        # Must be SELECT
        if not sql_upper.startswith('SELECT'):
            return False
        return True

