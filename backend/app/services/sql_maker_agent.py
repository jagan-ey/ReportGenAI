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

_logger = logging.getLogger(__name__)


class SQLMakerAgent:
    def __init__(self, db_url: str):
        self.db_url = db_url
        self._llm = None
        self._schema_provider = SQLAgentService(db_url)
        self._knowledge_base = None  # Lazy initialization - only create when needed
        self._initialized = False

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
        
        # Get actual table list from database to enforce strict table usage
        actual_tables = []
        try:
            from app.services.schema_helper import get_all_tables
            from app.core.database import get_engine
            engine = get_engine()
            actual_tables = get_all_tables(engine)
            _logger.debug(f"SQLMaker: Found {len(actual_tables)} actual tables in database")
        except Exception as e:
            _logger.warning(f"SQLMaker could not get actual table list: {e}")
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
                # Use schema helper to get all tables, then check which ones are mentioned
                question_lower = question.lower()
                mentioned_tables = []
                try:
                    from app.services.schema_helper import get_tables_from_sql, get_all_tables
                    from app.core.database import get_engine
                    
                    # Get all tables from database dynamically
                    engine = get_engine()
                    all_tables = get_all_tables(engine)
                    
                    # Check which tables are mentioned in the question
                    for table in all_tables:
                        if table.lower() in question_lower:
                            mentioned_tables.append(table)
                except Exception as e:
                    _logger.debug(f"Could not get tables dynamically: {e}. Continuing without table filtering.")
                    mentioned_tables = None
                
                # Get relevant knowledge from vector DB
                domain_knowledge = self._knowledge_base.get_relevant_knowledge(
                    question=question,
                    table_names=mentioned_tables if mentioned_tables else None,
                    knowledge_types=['column_definition', 'table_schema', 'data_patterns', 'business_rule']
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
                
                decision_prompt = (
                    "You are a SQL query analyzer. Determine if the user's new question is asking for a MODIFICATION "
                    "of the previous SQL query, or if it's a completely different query.\n\n"
                    "Return ONLY a JSON object with this structure:\n"
                    '{"should_reuse": true/false, "reason": "brief explanation"}\n\n'
                    "Rules:\n"
                    "- Return should_reuse=true if:\n"
                    "  * The new question is clearly modifying the previous query (e.g., changing a number, date, or filter)\n"
                    "  * The new question uses phrases like 'do for', 'same but', 'also', 'change to', 'instead of'\n"
                    "  * The new question is about the same tables/data domain as the previous query\n"
                    "- Return should_reuse=false if:\n"
                    "  * The new question is about completely different tables or data (e.g., previous was about customers, new is about loans)\n"
                    "  * The new question has no relationship to the previous query\n"
                    "  * The new question is asking for something entirely different\n\n"
                    "Examples:\n"
                    "Previous: Customer ReKYC query\n"
                    "New: 'do for > 3 months'\n"
                    "→ should_reuse=true (explicit modification)\n\n"
                    "Previous: Customer ReKYC query\n"
                    "New: 'Show me all loans with tenure less than 15 months'\n"
                    "→ should_reuse=false (completely different: customers vs loans)\n\n"
                    "Previous: Loan query with tenure > 12\n"
                    "New: 'Tenure > 15'\n"
                    "→ should_reuse=true (same domain, modifying filter)\n"
                )
                
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
            system_prompt = (
                "You are SQLMaker, a specialist at MODIFYING existing SQL Server queries.\n"
                "CRITICAL: A PREVIOUS SQL QUERY will be provided that is RELATED to the new question. You MUST use it as the BASE and ONLY modify the specific parts mentioned in the new question.\n\n"
                "RULES FOR MODIFYING PREVIOUS SQL:\n"
                "1. PRESERVE the entire SELECT clause (all columns) - DO NOT change column names or add/remove columns unless explicitly asked.\n"
                "2. PRESERVE all table aliases (e.g., 'cla', 'sla') - use the exact same aliases.\n"
                "3. PRESERVE all JOIN conditions and table relationships.\n"
                "4. PRESERVE the ORDER BY clause if present.\n"
                "5. MODIFY ONLY the WHERE clause conditions that are mentioned in the new question.\n"
                "   - If new question changes a number (e.g., '> 12' to '> 15'), change ONLY that number.\n"
                "   - If new question adds a date condition, add it to WHERE but keep all existing conditions.\n"
                "   - If new question removes a condition, remove only that specific condition.\n"
                "6. DO NOT change table names, column names, or query structure.\n"
                "7. DO NOT regenerate the query from scratch - you are MODIFYING, not creating.\n\n"
                "Example:\n"
                "Previous SQL: SELECT t1.col1, t1.col2 FROM table1 t1 WHERE t1.col2 > 12\n"
                "New question: 'col2 > 15'\n"
                "Modified SQL: SELECT t1.col1, t1.col2 FROM table1 t1 WHERE t1.col2 > 15\n"
                "(ONLY the number changed, everything else is identical)\n\n"
                "STANDARD SQL GENERATION RULES (if previous SQL is not related or not provided):\n"
                "- Only generate a single SQL SELECT statement.\n"
                "- Use ONLY the tables available in the database schema provided.\n"
                "- Do NOT use markdown fences (no ```).\n"
                "- Do NOT use backticks.\n"
                "- Do NOT include explanations.\n"
                "- Use TOP (not LIMIT).\n"
                "- Prefer explicit column lists (avoid SELECT * unless truly necessary).\n"
                "- Include contextually relevant columns that would be useful in a business report.\n"
                "- Use the domain knowledge and schema information provided to understand valid values, business meanings, and relationships.\n"
                "- Use exact column names from the schema - do not guess or use aliases that don't exist.\n"
                "- If the request is ambiguous, make a reasonable assumption and still produce SQL.\n\n"
                "CRITICAL TABLE SELECTION RULES:\n"
                "- Use domain knowledge and schema information to identify the correct table type based on the user's question.\n"
                "- When user asks for specific entity types, use the schema and domain knowledge to find the appropriate tables.\n"
                "- Domain knowledge will provide business synonyms and table descriptions to help you match user's intent to the correct tables.\n"
                "- Example: If user asks for 'loan accounts', use domain knowledge to find tables related to loans, not other account types.\n"
                "- Example: If user asks for 'customer details', use domain knowledge to find customer-related tables and join them.\n\n"
                "IMPORTANT QUERYING RULES:\n"
                "- Use the schema information to determine which tables and columns to use.\n"
                "- JOIN tables when:\n"
                "  * User explicitly asks for related data (e.g., 'accounts with customer details', 'loans with customer info')\n"
                "  * User asks for data from multiple entities (e.g., 'accounts and their owners', 'loans and customers')\n"
                "  * The question requires data that spans multiple tables to be meaningful\n"
                "- Only use direct queries (no joins) when:\n"
                "  * User asks for data from a single table only\n"
                "  * All required columns exist in one table\n"
                "- Use domain knowledge and schema information to understand relationships between tables (look for common join keys like ID columns, foreign keys in the schema).\n"
                "- When joining, include relevant columns from ALL joined tables to provide rich, complete results.\n"
                "- Match column names exactly as they appear in the schema.\n"
            )
        else:
            # Original system prompt when no previous SQL
            system_prompt = (
                "You are SQLMaker, a specialist at writing SQL Server (T-SQL) SELECT queries.\n"
                "You MUST follow these rules:\n"
                "- Only generate a single SQL SELECT statement.\n"
                "- CRITICAL: Use ONLY the EXACT table names and column names from the database schema provided below.\n"
                "- NEVER invent, guess, or create table/column names (e.g., do NOT use 'LoanAccounts', 'Customers', 'LoanAccountID', 'CustomerID', 'FirstName', 'LastName' - these are generic examples, NOT actual table/column names).\n"
                "- ALWAYS use the exact table and column names as they appear in the schema information provided.\n"
                "- Do NOT use markdown fences (no ```).\n"
                "- Do NOT use backticks.\n"
                "- Do NOT include explanations.\n"
                "- Use TOP (not LIMIT).\n"
                "- Prefer explicit column lists (avoid SELECT * unless truly necessary).\n"
                "- Include contextually relevant columns that would be useful in a business report.\n"
                "- Use the domain knowledge and schema information provided to understand valid values, business meanings, and relationships.\n"
                "- Use exact column names from the schema - do not guess or use aliases that don't exist.\n"
                "- If the request is ambiguous, make a reasonable assumption and still produce SQL using actual schema tables/columns.\n\n"
                "CRITICAL TABLE SELECTION RULES:\n"
                "- You MUST use ONLY tables that exist in the database. A list of ACTUAL table names will be provided below.\n"
                "- NEVER invent, guess, or create table names (e.g., do NOT use 'customer_dim', 'loan_dim', 'account_dim' - these are generic examples, NOT actual table names).\n"
                "- Use domain knowledge and schema information to identify the correct table type based on the user's question.\n"
                "- When user asks for specific entity types, use the schema and domain knowledge to find the appropriate tables FROM THE ACTUAL TABLE LIST.\n"
                "- Domain knowledge will provide business synonyms and table descriptions to help you match user's intent to the correct tables.\n"
                "- Example: If user asks for 'loan accounts', use domain knowledge to find tables related to loans FROM THE ACTUAL TABLE LIST.\n"
                "- Example: If user asks for 'customer details', use domain knowledge to find customer-related tables FROM THE ACTUAL TABLE LIST and join them.\n"
                "- If a table name is NOT in the actual table list, you MUST NOT use it - find an alternative from the actual list.\n\n"
                "IMPORTANT QUERYING RULES:\n"
                "- Use the schema information to determine which tables and columns to use.\n"
                "- JOIN tables when:\n"
                "  * User explicitly asks for related data (e.g., 'accounts with customer details', 'loans with customer info')\n"
                "  * User asks for data from multiple entities (e.g., 'accounts and their owners', 'loans and customers')\n"
                "  * The question requires data that spans multiple tables to be meaningful\n"
                "- Only use direct queries (no joins) when:\n"
                "  * User asks for data from a single table only\n"
                "  * All required columns exist in one table\n"
                "- Use domain knowledge and schema information to understand relationships between tables (look for common join keys like ID columns, foreign keys in the schema).\n"
                "- When joining, include relevant columns from ALL joined tables to provide rich, complete results.\n"
                "- Match column names exactly as they appear in the schema.\n"
            )

        # Build user prompt with schema + domain knowledge
        user_prompt_parts = [
            f"User question:\n{question}\n",
        ]
        
        # Add previous SQL query if available and related (for incremental modifications)
        if previous_sql_query and previous_sql_query.strip() and should_reuse_previous_sql:
            user_prompt_parts.append(
                f"\n{'='*80}\n"
                f"PREVIOUS SQL QUERY (RELATED TO NEW QUESTION - USE AS BASE):\n"
                f"{'='*80}\n"
                f"{previous_sql_query}\n"
                f"{'='*80}\n"
            )
            user_prompt_parts.append(
                "\nCRITICAL INSTRUCTIONS:\n"
                "1. The user's new question is asking for a MODIFICATION of the previous query.\n"
                "2. Copy the ENTIRE previous SQL query.\n"
                "3. Identify what changed in the new question (e.g., '> 12' became '> 15', or '> 6 months' became '> 3 months').\n"
                "4. Modify ONLY that specific part in the WHERE clause.\n"
                "5. Keep EVERYTHING else identical: SELECT columns, table aliases, JOINs, ORDER BY.\n"
                "6. Return the modified SQL query.\n\n"
                "DO NOT:\n"
                "- Change column names or add/remove columns\n"
                "- Change table aliases\n"
                "- Change JOIN conditions\n"
                "- Regenerate the query from scratch\n"
                "- Use different table names\n\n"
            )
        elif previous_sql_query and previous_sql_query.strip() and not should_reuse_previous_sql:
            # Previous SQL exists but is NOT related - ignore it and generate new query
            user_prompt_parts.append(
                "\nNOTE: A previous SQL query exists but is NOT related to this question. "
                "Generate a NEW query based on the user's question, ignoring the previous SQL.\n"
            )
        
        if domain_knowledge:
            user_prompt_parts.append(f"Domain Knowledge:\n{domain_knowledge[:3000]}\n")  # Limit domain knowledge to 3000 chars
        
        # Add ACTUAL table list with STRICT enforcement
        if actual_tables:
            user_prompt_parts.append(
                f"\n{'='*80}\n"
                f"CRITICAL: ACTUAL TABLES IN DATABASE (USE ONLY THESE - DO NOT INVENT OTHERS):\n"
                f"{'='*80}\n"
                f"{', '.join(sorted(actual_tables))}\n"
                f"{'='*80}\n"
                f"\nSTRICT RULE: You MUST use ONLY table names from the list above. "
                f"If you need a table that is NOT in this list, you MUST find an alternative from this list. "
                f"NEVER invent table names like 'customer_dim', 'loan_dim', etc. - use the EXACT names from the list above.\n\n"
            )
        
        # Increase schema info limit to ensure LLM has enough context
        schema_context = schema_info or ""
        user_prompt_parts.append(f"Database schema (CRITICAL - USE EXACT TABLE AND COLUMN NAMES FROM HERE):\n{schema_context[:5000]}\n")  # Increased to 5000 chars
        user_prompt_parts.append(
            "\nCRITICAL REMINDER:\n"
            "- The schema above contains the ACTUAL table names and column names in the database.\n"
            "- You MUST use ONLY these exact names - do NOT invent generic names.\n"
            "- Use the EXACT table and column names as they appear in the schema provided above.\n"
            "- Domain knowledge will help you understand which tables/columns to use, but you must use the EXACT names from the schema.\n"
            "- If a table name is NOT in the actual table list provided above, you MUST NOT use it.\n\n"
            "Return ONLY the SQL query text."
        )
        
        user_prompt = "\n".join(user_prompt_parts)

        from langchain_core.messages import SystemMessage, HumanMessage

        # Pass 1: draft SQL
        resp = self._llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])
        raw = resp.content if hasattr(resp, "content") else str(resp)
        sql1 = self._clean_and_extract(raw)

        ok1, reason1 = self._validate_candidate(sql1)
        if ok1:
            return {"success": True, "sql_query": sql1, "attempt": 1}

        # Pass 2: self-repair using validation feedback (still no explanations; SQL only)
        repair_prompt = self._build_repair_prompt(question, schema_info, sql1, reason1)
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

    def _build_repair_prompt(self, question: str, schema_info: str, bad_sql: str, failure_reason: str) -> str:
        # Get domain knowledge for repair attempt too
        try:
            domain_knowledge = self._knowledge_base.get_context_for_sql_generation(question)
        except Exception as e:
            domain_knowledge = ""
            _logger.warning(f"SQLMaker could not load domain knowledge for repair: {e}")
        
        # Get actual table list for repair prompt too
        actual_tables_repair = []
        try:
            from app.services.schema_helper import get_all_tables
            from app.core.database import get_engine
            engine = get_engine()
            actual_tables_repair = get_all_tables(engine)
        except Exception as e:
            _logger.debug(f"Could not get actual table list for repair: {e}")
            actual_tables_repair = []
        
        prompt_parts = [
            "Your previous SQL draft was rejected. Fix it.\n",
            "You MUST return ONLY a single valid SQL Server SELECT query.\n",
            "CRITICAL RULES:\n",
            "- Use ONLY the EXACT table names and column names from the database schema provided below.\n",
            "- NEVER invent, guess, or create table/column names (e.g., do NOT use 'LoanAccounts', 'Customers', 'LoanAccountID', 'CustomerID', 'FirstName', 'LastName').\n",
            "- ALWAYS use the exact table and column names as they appear in the schema information.\n",
            "- Only use tables from the provided schema.\n",
            "- No markdown, no backticks, no explanations.\n",
            "- Use TOP not LIMIT.\n",
            "- Use exact valid values from domain knowledge.\n",
            "- Use domain knowledge and schema information to identify the correct tables based on the user's question.\n",
            "- When user asks for related data (e.g., 'customer details', 'account owner info'), you MUST join with the appropriate related tables to get complete information.\n",
            "- JOIN tables when user explicitly requests related data from multiple entities.\n",
            "- Include relevant columns from ALL joined tables to provide complete results.\n\n",
            f"User question:\n{question}\n\n"
        ]
        
        if domain_knowledge:
            prompt_parts.append(f"Domain Knowledge:\n{domain_knowledge[:2000]}\n\n")
        
        # Add actual table list to repair prompt
        if actual_tables_repair:
            prompt_parts.append(
                f"\n{'='*80}\n"
                f"CRITICAL: ACTUAL TABLES IN DATABASE (USE ONLY THESE - DO NOT INVENT OTHERS):\n"
                f"{'='*80}\n"
                f"{', '.join(sorted(actual_tables_repair))}\n"
                f"{'='*80}\n"
                f"\nSTRICT RULE: You MUST use ONLY table names from the list above. "
                f"If you need a table that is NOT in this list, you MUST find an alternative from this list. "
                f"NEVER invent table names like 'customer_dim', 'loan_dim', etc. - use the EXACT names from the list above.\n\n"
            )
        
        prompt_parts.extend([
            f"Database schema (CRITICAL - USE EXACT TABLE AND COLUMN NAMES FROM HERE):\n{(schema_info or '')[:5000]}\n\n",
            "CRITICAL REMINDER:\n"
            "- The schema above contains the ACTUAL table names and column names in the database.\n"
            "- You MUST use ONLY these exact names - do NOT invent generic names.\n"
            "- Use the EXACT table and column names as they appear in the schema.\n"
            "- If a table name is NOT in the actual table list provided above, you MUST NOT use it.\n\n",
            f"Previous SQL draft:\n{bad_sql}\n\n",
            f"Why it failed:\n{failure_reason}\n\n",
            "Return the corrected SQL now:"
        ])
        
        return "".join(prompt_parts)

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


