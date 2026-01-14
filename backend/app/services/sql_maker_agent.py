"""
SQLMaker Agent (LLM)

Specialized LLM agent that generates a SQL Server SELECT query for report/data questions
using ONLY the 8 BIU Star Schema tables. It does not execute SQL.
"""

from typing import Optional, Dict, Any
import logging
import re
import json

from app.core.config import settings
from app.services.sql_agent import SQLAgentService
from app.services.vector_knowledge_base import get_vector_knowledge_base
from app.services.prompt_loader import get_prompt_loader

_logger = logging.getLogger(__name__)


class SQLMakerAgent:
    def __init__(self, db_url: str):
        self.db_url = db_url
        self._llm = None
        self._schema_provider = SQLAgentService(db_url)
        self._knowledge_base = None  # Lazy initialization - only create when needed
        self._initialized = False
        self._prompt_loader = get_prompt_loader()

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
            _logger.error(f"Failed to initialize SQLMaker LLM: {e}")
            self._llm = None
            self._initialized = True

    def generate_sql(self, question: str, previous_sql_query: Optional[str] = None) -> Dict[str, Any]:
        """
        Returns:
          { success: True, sql_query: str }
          { success: False, error: str, sql_query: Optional[str] }
        """
        self._ensure_initialized()
        if not self._llm:
            return {
                "success": False,
                "error": "SQLMaker LLM not available. Check Azure OpenAI configuration.",
                "sql_query": None,
            }

        try:
            schema_info = self._schema_provider.get_schema_info()
        except Exception as e:
            schema_info = ""
            _logger.warning(f"SQLMaker could not load schema info: {e}")
        
        # Get actual table list from KB database to enforce strict table usage
        # SQLMaker should only use tables from KB database (regulatory_data_mart), not app database
        actual_tables = []
        try:
            from app.services.schema_helper import get_all_tables
            from app.core.database import get_kb_engine
            engine = get_kb_engine()
            actual_tables = get_all_tables(engine)
            _logger.debug(f"SQLMaker: Found {len(actual_tables)} actual tables in KB database")
        except Exception as e:
            _logger.warning(f"SQLMaker could not get actual table list from KB database: {e}")
            actual_tables = []

        # Get domain knowledge context from vector knowledge base (lazy initialization)
        domain_knowledge = None
        try:
            # Lazy initialize vector KB only when needed
            if self._knowledge_base is None:
                try:
                    self._knowledge_base = get_vector_knowledge_base()
                except Exception as e:
                    _logger.debug(f"Vector KB not available: {e}. Continuing without it.")
                    self._knowledge_base = None
            
            # Only try to use vector KB if it's actually initialized and working
            if (self._knowledge_base and 
                hasattr(self._knowledge_base, '_initialized') and 
                self._knowledge_base._initialized and
                hasattr(self._knowledge_base, 'collection') and
                self._knowledge_base.collection is not None):
                
                # Extract table names from question dynamically
                # Use schema helper to get all tables from KB database, then check which ones are mentioned
                question_lower = question.lower()
                mentioned_tables = []
                try:
                    from app.services.schema_helper import get_tables_from_sql, get_all_tables
                    from app.core.database import get_kb_engine
                    
                    # Get all tables from KB database dynamically (not app database)
                    engine = get_kb_engine()
                    all_tables = get_all_tables(engine)
                    
                    # Check which tables are mentioned in the question
                    for table in all_tables:
                        if table.lower() in question_lower:
                            mentioned_tables.append(table)
                except Exception as e:
                    _logger.debug(f"Could not get tables dynamically: {e}. Continuing without table filtering.")
                    mentioned_tables = None
                
                # Get relevant knowledge from vector DB with enhanced retrieval
                domain_knowledge = self._knowledge_base.get_relevant_knowledge(
                    question=question,
                    table_names=mentioned_tables if mentioned_tables else None,
                    knowledge_types=['column_definition', 'table_schema', 'data_patterns', 'business_rule'],
                    max_results=10,  # Get top 10 most relevant chunks
                    min_relevance_score=None  # Return all results, sorted by relevance
                )
        except Exception as e:
            _logger.debug(f"Could not retrieve knowledge from vector KB: {e}. Continuing without it.")
            domain_knowledge = None
        except Exception as e:
            domain_knowledge = ""
            _logger.warning(f"SQLMaker could not load domain knowledge: {e}")

        # Use LLM to intelligently decide if previous SQL should be reused
        should_reuse_previous_sql = False
        if previous_sql_query and previous_sql_query.strip():
            # Ask LLM to decide if the previous SQL is related to the new question
            try:
                from langchain_core.messages import SystemMessage, HumanMessage
                
                decision_prompt = self._prompt_loader.get_prompt("sql_maker", "decision_prompt")
                
                decision_input = json.dumps({
                    "previous_sql_query": previous_sql_query[:500],  # Truncate for token efficiency
                    "new_question": question
                }, ensure_ascii=False)
                
                decision_resp = self._llm.invoke([
                    SystemMessage(content=decision_prompt),
                    HumanMessage(content=decision_input)
                ])
                decision_text = decision_resp.content if hasattr(decision_resp, "content") else str(decision_resp)
                
                # Parse LLM response
                import json as json_module
                try:
                    decision_json = json_module.loads(decision_text)
                    should_reuse_previous_sql = decision_json.get("should_reuse", False)
                    _logger.info(f"LLM decision: should_reuse={should_reuse_previous_sql}, reason={decision_json.get('reason', 'N/A')}")
                except Exception as e:
                    _logger.warning(f"Could not parse LLM decision, defaulting to false: {e}")
                    should_reuse_previous_sql = False
            except Exception as e:
                _logger.warning(f"LLM decision failed, defaulting to false: {e}")
                should_reuse_previous_sql = False
        
        # Build system prompt - prioritize previous SQL reuse if LLM determined it's related
        if previous_sql_query and previous_sql_query.strip() and should_reuse_previous_sql:
            system_prompt = self._prompt_loader.get_prompt("sql_maker", "system_prompt_modify")
        else:
            # Original system prompt when no previous SQL
            system_prompt = self._prompt_loader.get_prompt("sql_maker", "system_prompt_new")

        # Build user prompt with schema + domain knowledge using template
        previous_sql_section = ""
        if previous_sql_query and previous_sql_query.strip() and should_reuse_previous_sql:
            previous_sql_section = self._prompt_loader.get_prompt(
                "sql_maker",
                "user_prompt_modify_section",
                previous_sql_query=previous_sql_query
            )
        elif previous_sql_query and previous_sql_query.strip() and not should_reuse_previous_sql:
            previous_sql_section = self._prompt_loader.get_prompt("sql_maker", "user_prompt_unrelated_section")
        
        domain_knowledge_section = ""
        if domain_knowledge:
            domain_knowledge_section = f"Domain Knowledge:\n{domain_knowledge[:3000]}\n"
        
        actual_tables_section = ""
        if actual_tables:
            actual_tables_section = (
                f"\n{'='*80}\n"
                f"CRITICAL: ACTUAL TABLES IN DATABASE (USE ONLY THESE - DO NOT INVENT OTHERS):\n"
                f"{'='*80}\n"
                f"{', '.join(sorted(actual_tables))}\n"
                f"{'='*80}\n"
                f"\nSTRICT RULE: You MUST use ONLY table names from the list above. "
                f"If you need a table that is NOT in this list, you MUST find an alternative from this list. "
                f"NEVER invent table names like 'customer_dim', 'loan_dim', etc. - use the EXACT names from the list above.\n\n"
            )
        
        # Get actual column names for tables mentioned in domain knowledge
        # This helps prevent generic column name generation by showing actual column names
        # NO HARDCODED KEYWORDS - rely entirely on domain knowledge from vector KB
        actual_columns_section = ""
        try:
            from app.services.schema_helper import get_table_columns
            from app.core.database import get_kb_engine
            
            # Identify tables based ONLY on domain knowledge (no hardcoded keywords)
            likely_tables = []
            
            # Extract table names that appear in domain knowledge
            # Domain knowledge should contain table names and their business context
            if domain_knowledge and actual_tables:
                domain_lower = domain_knowledge.lower()
                for table in actual_tables:
                    # Check if table name appears in domain knowledge (with variations)
                    table_variations = [
                        table.lower(),
                        table.replace('_', ' ').lower(),
                        table.replace('_', '').lower()
                    ]
                    if any(var in domain_lower for var in table_variations):
                        if table not in likely_tables:
                            likely_tables.append(table)
            
            # Limit to 3 tables max to avoid token bloat
            likely_tables = likely_tables[:3]
            
            # Get column information for tables identified from domain knowledge
            if likely_tables:
                engine = get_kb_engine()
                columns_info_parts = []
                for table in likely_tables:
                    try:
                        columns = get_table_columns(engine, table)
                        if columns:
                            cols_str = "\n  ".join([f"{col['name']} ({col['type']})" for col in columns])
                            columns_info_parts.append(f"{table}:\n  {cols_str}")
                            _logger.debug(f"SQLMaker: Got {len(columns)} columns for table {table}")
                    except Exception as e:
                        _logger.debug(f"Could not get columns for {table}: {e}")
                
                if columns_info_parts:
                    actual_columns_section = (
                        f"\n{'='*80}\n"
                        f"CRITICAL: ACTUAL COLUMN NAMES FOR RELEVANT TABLES (USE ONLY THESE EXACT NAMES):\n"
                        f"{'='*80}\n"
                        f"{chr(10).join(columns_info_parts)}\n"
                        f"{'='*80}\n"
                        f"\nSTRICT RULES:\n"
                        f"1. You MUST use ONLY the exact column names listed above (case-sensitive).\n"
                        f"2. Do NOT invent generic column names - use the EXACT names from the list above.\n"
                        f"3. Match the user's question intent to the actual column names from the schema.\n"
                        f"4. Use domain knowledge to understand which columns represent status, dates, amounts, etc.\n\n"
                    )
                    _logger.info(f"SQLMaker: Added actual column info for {len(likely_tables)} tables from domain knowledge: {likely_tables}")
        except Exception as e:
            _logger.warning(f"SQLMaker could not get actual column information: {e}")
        
        schema_context = schema_info or ""
        user_prompt = self._prompt_loader.get_prompt(
            "sql_maker",
            "user_prompt_template",
            question=question,
            previous_sql_section=previous_sql_section,
            domain_knowledge_section=domain_knowledge_section,
            actual_tables_section=actual_tables_section,
            actual_columns_section=actual_columns_section,
            schema_context=schema_context[:5000]
        )

        from langchain_core.messages import SystemMessage, HumanMessage

        # Pass 1: draft SQL
        resp = self._llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])
        raw = resp.content if hasattr(resp, "content") else str(resp)
        sql1 = self._clean_and_extract(raw)

        ok1, reason1 = self._validate_candidate(sql1)
        if ok1:
            return {"success": True, "sql_query": sql1, "attempt": 1}

        # Pass 2: self-repair using validation feedback (still no explanations; SQL only)
        repair_prompt = self._build_repair_prompt(question, schema_info, sql1, reason1, actual_tables, actual_columns_section)
        resp2 = self._llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=repair_prompt)])
        raw2 = resp2.content if hasattr(resp2, "content") else str(resp2)
        sql2 = self._clean_and_extract(raw2)

        ok2, reason2 = self._validate_candidate(sql2)
        if ok2:
            return {"success": True, "sql_query": sql2, "attempt": 2}

        # Still failed after repair
        return {
            "success": False,
            "error": f"SQLMaker could not generate a valid SQL query (attempt1: {reason1}; attempt2: {reason2}).",
            "sql_query": sql2 or sql1 or None,
        }

    def _clean_and_extract(self, raw_text: str) -> str:
        sql = self._extract_sql(raw_text)
        sql = self._schema_provider._clean_sql_string(sql) if hasattr(self._schema_provider, "_clean_sql_string") else sql
        return sql.strip()

    def _validate_candidate(self, sql: str) -> (bool, str):
        if not sql:
            return False, "empty_sql"
        # Prefer the same validator used elsewhere (blocks unsafe ops, requires SELECT)
        if hasattr(self._schema_provider, "validate_sql"):
            if not self._schema_provider.validate_sql(sql):
                return False, "failed_validate_sql"
        # Extra cheap guardrails
        if "SELECT" not in sql.upper():
            return False, "missing_select"
        if "`" in sql:
            return False, "contains_backticks"
        if "```" in sql:
            return False, "contains_fences"
        return True, "ok"

    def _build_repair_prompt(self, question: str, schema_info: str, bad_sql: str, failure_reason: str, actual_tables: list = None, actual_columns_section: str = "") -> str:
        # Get domain knowledge for repair attempt too
        try:
            domain_knowledge = self._knowledge_base.get_context_for_sql_generation(question)
        except Exception as e:
            domain_knowledge = ""
            _logger.warning(f"SQLMaker could not load domain knowledge for repair: {e}")
        
        # Get actual table list from KB database for repair prompt too
        actual_tables_repair = actual_tables or []
        if not actual_tables_repair:
            try:
                from app.services.schema_helper import get_all_tables
                from app.core.database import get_kb_engine
                engine = get_kb_engine()
                actual_tables_repair = get_all_tables(engine)
            except Exception as e:
                _logger.debug(f"Could not get actual table list for repair: {e}")
                actual_tables_repair = []
        
        domain_knowledge_section = ""
        if domain_knowledge:
            domain_knowledge_section = f"Domain Knowledge:\n{domain_knowledge[:2000]}\n\n"
        
        actual_tables_section = ""
        if actual_tables_repair:
            actual_tables_section = (
                f"\n{'='*80}\n"
                f"CRITICAL: ACTUAL TABLES IN DATABASE (USE ONLY THESE - DO NOT INVENT OTHERS):\n"
                f"{'='*80}\n"
                f"{', '.join(sorted(actual_tables_repair))}\n"
                f"{'='*80}\n"
                f"\nSTRICT RULE: You MUST use ONLY table names from the list above. "
                f"If you need a table that is NOT in this list, you MUST find an alternative from this list. "
                f"NEVER invent table names like 'customer_dim', 'loan_dim', etc. - use the EXACT names from the list above.\n\n"
            )
        
        # If actual_columns_section was not provided, try to get it for repair
        repair_columns_section = actual_columns_section
        if not repair_columns_section:
            try:
                from app.services.schema_helper import get_table_columns
                from app.core.database import get_kb_engine
                
                # Extract table names from domain knowledge (NO HARDCODED KEYWORDS)
                likely_tables = []
                if domain_knowledge and actual_tables_repair:
                    domain_lower = domain_knowledge.lower()
                    for table in actual_tables_repair:
                        table_variations = [
                            table.lower(),
                            table.replace('_', ' ').lower(),
                            table.replace('_', '').lower()
                        ]
                        if any(var in domain_lower for var in table_variations):
                            if table not in likely_tables:
                                likely_tables.append(table)
                
                if likely_tables:
                    engine = get_kb_engine()
                    columns_info_parts = []
                    for table in likely_tables[:2]:  # Limit to 2 for repair
                        try:
                            columns = get_table_columns(engine, table)
                            if columns:
                                cols_str = "\n  ".join([f"{col['name']} ({col['type']})" for col in columns])
                                columns_info_parts.append(f"{table}:\n  {cols_str}")
                        except Exception as e:
                            _logger.debug(f"Could not get columns for {table} in repair: {e}")
                    
                    if columns_info_parts:
                        repair_columns_section = (
                            f"\n{'='*80}\n"
                            f"CRITICAL: ACTUAL COLUMN NAMES FOR RELEVANT TABLES (USE ONLY THESE EXACT NAMES):\n"
                            f"{'='*80}\n"
                            f"{chr(10).join(columns_info_parts)}\n"
                            f"{'='*80}\n"
                            f"\nSTRICT RULES: Use ONLY the exact column names listed above. Do NOT invent generic names.\n\n"
                        )
            except Exception as e:
                _logger.debug(f"Could not get column info for repair: {e}")
        
        return self._prompt_loader.get_prompt(
            "sql_maker",
            "repair_prompt_template",
            question=question,
            domain_knowledge_section=domain_knowledge_section,
            actual_tables_section=actual_tables_section,
            actual_columns_section=repair_columns_section,
            schema_info=(schema_info or '')[:5000],
            bad_sql=bad_sql,
            failure_reason=failure_reason
        )

    def _extract_sql(self, text: str) -> str:
        if not text:
            return ""

        # Strip markdown fences if model ignored instructions
        text = re.sub(r"```sql\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"```", "", text)

        # Take substring starting at the first SELECT
        m = re.search(r"\bSELECT\b", text, flags=re.IGNORECASE)
        if m:
            text = text[m.start() :]

        # If it returned multiple statements, keep first SELECT statement-ish chunk
        # (best-effort; validator will still block non-SELECT ops)
        parts = re.split(r";\s*\n|\n\s*\n", text)
        candidate = parts[0].strip() if parts else text.strip()

        return candidate.strip()


