"""
Conversational Agent for handling non-SQL queries
Uses LLM to generate natural, contextual responses for conversational queries
"""
from typing import Dict, Any, Optional
from app.core.config import settings
import logging
import re
import datetime as _dt

from sqlalchemy import text, bindparam
from sqlalchemy import create_engine

_logger = logging.getLogger(__name__)


class ConversationalAgent:
    """
    Handles conversational queries that don't require SQL generation
    Uses LLM to generate natural, contextual responses
    Examples: greetings, capability questions, schema inquiries
    """
    
    def __init__(self, db_url: str = None):
        self.db_url = db_url
        self._llm = None
        self._sql_agent = None
        self._engine = None
        self._initialized = False
    
    def _ensure_initialized(self):
        """Lazy initialization of LLM and schema access"""
        if self._initialized:
            return
        
        try:
            # Initialize Azure OpenAI LLM for conversational responses
            from langchain_openai import AzureChatOpenAI
            
            self._llm = AzureChatOpenAI(
                azure_endpoint=settings.AZURE_ENDPOINT,
                api_key=settings.OPENAI_API_KEY,
                api_version=settings.AZURE_API_VERSION,
                deployment_name=settings.AZURE_DEPLOYMENT_NAME,
                temperature=0.7  # Slightly higher for more natural conversation
            )
            _logger.info("✅ Conversational LLM initialized")
            
            # For schema-related questions, we need access to schema info
            if self.db_url:
                from app.services.sql_agent import SQLAgentService
                self._sql_agent = SQLAgentService(self.db_url)
                _logger.info("✅ Schema access initialized for conversational agent")

                # Also keep a lightweight SQLAlchemy engine for metadata lookups (freshness, max dates, etc.)
                try:
                    self._engine = create_engine(self.db_url, pool_pre_ping=True)
                except Exception as e:
                    _logger.warning(f"Could not create SQLAlchemy engine for conversational agent: {e}")
                    self._engine = None
            
            self._initialized = True
        except Exception as e:
            _logger.error(f"Failed to initialize conversational agent: {str(e)}")
            self._llm = None
            self._sql_agent = None
            self._initialized = True
    
    def is_conversational_query(self, question: str) -> bool:
        """
        Detect if a query is conversational (doesn't need SQL generation)
        """
        question_lower = question.lower().strip()
        
        # Greetings and casual conversation
        greetings = ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening']
        if any(question_lower.startswith(g) for g in greetings):
            return True
        
        # Questions about capabilities
        capability_keywords = [
            'what can you do', 'what do you do', 'help', 'capabilities', 
            'features', 'what are you', 'who are you', 'introduction'
        ]
        if any(keyword in question_lower for keyword in capability_keywords):
            return True
        
        # Questions about schema/tables (informational, not SQL generation)
        schema_keywords = [
            'what tables', 'which tables', 'list tables', 'show tables',
            'how many tables', 'how many table',
            'what columns', 'which columns', 'list columns', 'show columns',
            'how many columns', 'how many column',
            'tables have', 'table has', 'tables with', 'table with',
            'columns in', 'column in', 'fields in', 'field in',
            'schema', 'database structure', 'table structure',
            'kyc related', 'kyc field', 'kyc column'
        ]
        if any(keyword in question_lower for keyword in schema_keywords):
            return True
        
        # Questions about the system
        system_keywords = [
            'how does this work', 'how to use', 'how do i', 'tutorial',
            'guide', 'instructions', 'explain'
        ]
        if any(keyword in question_lower for keyword in system_keywords):
            return True
        
        return False
    
    def handle_query(self, question: str, previous_sql_query: Optional[str] = None) -> Dict[str, Any]:
        """
        Handle conversational query using LLM to generate natural response
        """
        self._ensure_initialized()
        
        if not self._llm:
            # Fallback if LLM not available
            return {
                "success": True,
                "answer": "I'm here to help you query your data using natural language. Please ask me questions about your data, or use predefined queries from the sidebar.",
                "sql_query": None,
                "is_conversational": True
            }
        
        # Get schema information if needed for context
        schema_context = ""
        question_lower = question.lower().strip()
        
        # For schema-related questions, include schema info
        if any(keyword in question_lower for keyword in [
            'table', 'column', 'schema', 'field', 'kyc', 'structure'
        ]):
            try:
                if self._sql_agent:
                    schema_info = self._sql_agent.get_schema_info()
                    # Include relevant parts of schema (first 2000 chars to avoid token limits)
                    schema_context = f"\n\nDatabase Schema Information:\n{schema_info[:2000]}"
            except Exception as e:
                _logger.warning(f"Could not get schema info: {str(e)}")
        
        # Build prompt for LLM
        system_prompt = """You are a helpful assistant for the GenAI Continuous Controls Monitoring (CCM) Platform. 
You help users understand the system, answer questions about the database schema, and guide them on how to use the platform.

Key Information:
- The platform has access to database tables as defined in the schema
- Users can ask questions in natural language to query data
- There are predefined queries available in the sidebar for 100% accuracy
- The platform supports report download, approval workflows, and scheduling

Your role:
- Answer questions about the platform's capabilities
- Explain how to use the system
- Provide information about database tables and columns when asked
- Be friendly, helpful, and concise
- If asked about data, suggest using natural language queries or predefined queries

IMPORTANT: Do NOT generate SQL queries. This is a conversational response only. If the user wants to query data, they should ask data questions which will be handled by the SQL agent."""

        # Few-shot guidance for follow-ups about the last result
        system_prompt += """

Behavior for follow-up/meta questions:
- If "Previous SQL" and "Source tables used in the previous SQL" are provided, use them to answer questions about:
  - where the data came from (tables)
  - what was executed (high-level explanation of the SQL intent)
  - how the result was derived
- Do NOT generate new SQL.

Examples:
User: "from which table we got this data?"
Context: Source tables used in the previous SQL: - table_name
Assistant: "The data came from the table table_name."

User: "are the data from this table fresh or old?"
Context: Freshness metadata (computed from database): - table_name: max(audit_column)=2025-11-30 10:05:00 (lag_days=16)
Assistant: "The latest update in table_name is 2025-11-30 (16 days behind today). The data is older; confirm if you want to proceed."
"""
        
        prior_sql_context = ""
        source_tables_context = ""
        freshness_context = ""
        if previous_sql_query:
            prior_sql_context = f"\n\nPrevious SQL (for context):\n{previous_sql_query}"
            try:
                tables = self._extract_tables_from_sql(previous_sql_query)
                if tables:
                    source_tables_context = "\n\nSource tables used in the previous SQL:\n" + "\n".join(
                        [f"- {t}" for t in tables]
                    )
                    # Compute real freshness signals (max date/timestamp + lag) and pass to LLM
                    freshness = self._compute_freshness(tables)
                    if freshness:
                        freshness_context = (
                            "\n\nFreshness metadata (computed from database):\n"
                            + "\n".join(
                                [
                                    f"- {t}: max({meta.get('column')})={meta.get('max_value')} (lag_days={meta.get('lag_days')})"
                                    for t, meta in freshness.items()
                                ]
                            )
                        )
            except Exception:
                # Non-fatal; still pass previous SQL to LLM
                source_tables_context = ""
                freshness_context = ""

        user_prompt = f"""User Question: {question}{schema_context}{prior_sql_context}{source_tables_context}{freshness_context}

Please provide a helpful, natural response to this question. Be concise but informative."""
        
        try:
            # Use LLM to generate response
            from langchain_core.messages import HumanMessage, SystemMessage
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = self._llm.invoke(messages)
            answer = response.content if hasattr(response, 'content') else str(response)
            
            _logger.info(f"✅ Conversational LLM response generated for: {question[:50]}")
            
            return {
                "success": True,
                "answer": answer,
                "sql_query": None,
                "is_conversational": True
            }
        except Exception as e:
            _logger.error(f"Error generating conversational response: {str(e)}")
            # Fallback response
            return {
                "success": True,
                "answer": f"I understand you're asking: '{question}'. I'm designed to help you query your database using natural language. If you're looking for data, try asking questions like 'List customers by state' or 'How many accounts are active?'. You can also browse predefined queries from the sidebar for guaranteed accurate results!",
                "sql_query": None,
                "is_conversational": True
            }

    def _compute_freshness(self, tables: list) -> Dict[str, Dict[str, Any]]:
        """
        Compute per-table freshness using real DB values.
        Prefers audit columns (configurable via AUDIT_COLUMNS setting), else best max across other date-like columns.
        Returns dict: { table: {column, max_value, lag_days} }
        """
        if not self._engine or not tables:
            return {}

        today = _dt.date.today()
        freshness: Dict[str, Dict[str, Any]] = {}

        # Load columns for these tables
        cols_q = (
            text(
                """
                SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = 'dbo'
                  AND TABLE_NAME IN :tables
                """
            )
            .bindparams(bindparam("tables", expanding=True))
        )

        with self._engine.connect() as conn:
            rows = conn.execute(cols_q, {"tables": list(tables)}).fetchall()

            by_table: Dict[str, list] = {}
            for t, c, dt in rows:
                by_table.setdefault(t, []).append((c, (dt or "").lower()))

            date_types = {"date", "datetime", "datetime2", "smalldatetime", "datetimeoffset", "timestamp"}

            def _try_max(table: str, col: str):
                q = text(f"SELECT MAX([{col}]) AS max_val FROM dbo.[{table}]")
                return conn.execute(q).scalar()

            for t in tables:
                cols = by_table.get(t, [])
                if not cols:
                    continue

                # Candidates
                candidates = []
                for c, dt in cols:
                    name = (c or "").upper()
                    if dt in date_types or name.endswith("_DT") or name.endswith("_DATE") or "DATE" in name:
                        candidates.append(c)

                # Get audit column names from config (generic, not hardcoded)
                audit_columns = [col.strip().upper() for col in settings.AUDIT_COLUMNS.split(",") if col.strip()]
                
                preferred = []
                for c in audit_columns:
                    if any(colname.upper() == c for colname, _ in cols):
                        preferred.append(c)

                # Business date columns are those that aren't audit columns
                business = [c for c in sorted(set(candidates)) if c.upper() not in audit_columns]

                chosen_col = None
                max_val = None

                # Prefer audit columns
                for c in preferred:
                    v = _try_max(t, c)
                    if v is not None:
                        chosen_col = c
                        max_val = v
                        break

                # Else best business date
                if max_val is None and business:
                    best = None
                    best_col = None
                    for c in business[:8]:
                        v = _try_max(t, c)
                        if v is not None and (best is None or v > best):
                            best = v
                            best_col = c
                    if best is not None:
                        chosen_col = best_col
                        max_val = best

                if chosen_col:
                    lag_days = None
                    try:
                        max_date = max_val.date() if hasattr(max_val, "date") else max_val
                        if isinstance(max_date, _dt.date):
                            lag_days = (today - max_date).days
                    except Exception:
                        lag_days = None

                    freshness[t] = {
                        "column": chosen_col,
                        "max_value": str(max_val) if max_val is not None else None,
                        "lag_days": lag_days,
                    }

        return freshness

    def _extract_tables_from_sql(self, sql: str) -> list:
        """
        Best-effort extraction of table names from SQL Server query.
        Returns unique table identifiers as strings (without schema brackets).
        """
        if not sql:
            return []
        cleaned = re.sub(r"```sql\s*|\s*```", "", sql, flags=re.IGNORECASE).strip()

        # Capture FROM/JOIN tokens; supports dbo.table, [dbo].[table], table alias
        pattern = re.compile(
            r"\b(?:FROM|JOIN)\s+((?:\[[^\]]+\]|\w+)(?:\.(?:\[[^\]]+\]|\w+))?)",
            re.IGNORECASE,
        )
        found = []
        for m in pattern.finditer(cleaned):
            ident = m.group(1)
            ident = ident.replace("[", "").replace("]", "")
            # Normalize dbo.table -> table (keep schema if not dbo)
            if "." in ident:
                schema, table = ident.split(".", 1)
                ident = table if schema.lower() in ("dbo",) else f"{schema}.{table}"
            found.append(ident)

        # Unique preserve order
        out = []
        seen = set()
        for t in found:
            if t and t not in seen:
                seen.add(t)
                out.append(t)
        return out
    

