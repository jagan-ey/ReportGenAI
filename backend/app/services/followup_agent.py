"""
FollowUp Agent (LLM)

An intelligent agent that analyzes user questions and generated SQL queries to identify
any ambiguities, missing information, or clarifications needed BEFORE executing the query.

The agent can ask ANY type of relevant follow-up question, including but not limited to:
- Date column selection (when ambiguous)
- Data freshness confirmation (when data is stale)
- Filter value clarification (when filters are vague)
- Join/relationship confirmation (when multiple join paths exist)
- Aggregation method selection (when ambiguous)
- Output format preferences
- Any other clarification needed to ensure accurate query execution

This agent returns a structured follow-up questionnaire (JSON) that the UI can present.
"""

from typing import Dict, Any, List, Optional, Tuple
import datetime as _dt
import json
import logging
import re

from sqlalchemy import text
from sqlalchemy import bindparam
from sqlalchemy.orm import Session

from app.core.config import settings

_logger = logging.getLogger(__name__)


class FollowUpAgentService:
    def __init__(self):
        self._llm = None
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
        except Exception as e:
            _logger.warning(f"FollowUpAgent LLM not available: {e}")
            self._llm = None
        self._initialized = True

    def analyze(
        self,
        *,
        db: Session,
        question: str,
        sql_query: str,
        today: Optional[_dt.date] = None,
    ) -> Dict[str, Any]:
        """
        Returns:
          {
            "needs_followup": bool,
            "followup_questions": [ ... ],
            "analysis": str
          }
        """
        today = today or _dt.date.today()

        tables = self._extract_tables_from_sql(sql_query)
        if not tables:
            return {"needs_followup": False, "followup_questions": [], "analysis": "No source tables detected."}

        # Validate that all tables actually exist in the database
        valid_tables = []
        invalid_tables = []
        try:
            from app.services.schema_helper import get_all_tables
            from app.core.database import get_kb_engine
            # Use KB engine for table validation (dimension tables are in KB DB)
            engine = get_kb_engine()
            actual_tables = set(t.upper() for t in get_all_tables(engine))
            
            for table in tables:
                if table.upper() in actual_tables:
                    valid_tables.append(table)
                else:
                    invalid_tables.append(table)
                    _logger.warning(f"FollowUp Agent: Table '{table}' does not exist in database")
        except Exception as e:
            _logger.warning(f"FollowUp Agent: Could not validate tables: {e}. Proceeding with all tables.")
            valid_tables = tables
            invalid_tables = []
        
        # If there are invalid tables, add this to schema context for LLM to know
        if invalid_tables:
            _logger.warning(f"FollowUp Agent: Found invalid tables in SQL: {invalid_tables}. These will be flagged in the prompt.")
        
        # Only process valid tables for date/freshness metadata
        table_date_cols, table_freshness = self._collect_date_metadata(db, valid_tables, today=today)
        date_cols_used = self._extract_date_columns_used_in_sql(sql_query, table_date_cols)

        # Filter freshness metadata to only include tables where lag_days exceeds threshold
        freshness_threshold = settings.DATA_FRESHNESS_THRESHOLD_DAYS
        filtered_freshness = {}
        for table, freshness_info in table_freshness.items():
            lag_days = freshness_info.get("lag_days")
            # Only include if lag_days is a number and exceeds threshold
            if lag_days is not None and isinstance(lag_days, (int, float)) and lag_days > freshness_threshold:
                filtered_freshness[table] = freshness_info
            else:
                _logger.debug(f"Excluding {table} from freshness check: lag_days={lag_days} (threshold={freshness_threshold})")

        # Get basic schema information for context (even if no date metadata)
        schema_context = self._get_schema_context(db, tables)

        # If LLM not available, do not block (avoid hardcoding behavior).
        self._ensure_initialized()
        if not self._llm:
            return {"needs_followup": False, "followup_questions": [], "analysis": "Follow-up agent unavailable."}

        prompt = self._build_prompt(
            question=question,
            sql_query=sql_query,
            tables=valid_tables,  # Only pass valid tables
            invalid_tables=invalid_tables,  # Pass invalid tables separately
            table_date_cols=table_date_cols,
            table_freshness=filtered_freshness,  # Use filtered freshness
            date_cols_used=date_cols_used,
            schema_context=schema_context,
            today=today,
        )

        from langchain_core.messages import SystemMessage, HumanMessage
        resp = self._llm.invoke([SystemMessage(content=self._system_prompt()), HumanMessage(content=prompt)])
        txt = resp.content if hasattr(resp, "content") else str(resp)

        parsed = self._safe_json(txt)
        if not isinstance(parsed, dict):
            return {"needs_followup": False, "followup_questions": [], "analysis": "Could not parse follow-up output."}

        needs = bool(parsed.get("needs_followup", False))
        questions = parsed.get("followup_questions") or []
        analysis = parsed.get("analysis") or ""

        # Minimal normalization
        if not isinstance(questions, list):
            questions = []

        return {"needs_followup": needs and len(questions) > 0, "followup_questions": questions, "analysis": analysis}

    def _system_prompt(self) -> str:
        return (
            "You are an intelligent follow-up question generator for a banking data assistant.\n"
            "Your job is to analyze user questions and generated SQL queries to identify ANY ambiguities, "
            "missing information, or clarifications needed BEFORE executing the SQL query.\n"
            "You must output ONLY valid JSON.\n\n"
            "Your goal is to ensure the query will execute correctly and return the data the user actually wants.\n\n"
            "Types of follow-up questions you can ask (not limited to these):\n"
            "1) Date/Time Ambiguity:\n"
            "   - Multiple date columns exist and the question doesn't specify which one to use\n"
            "   - The question is vague about time periods (e.g., 'recently', 'last month' without specifics)\n"
            "   - The SQL might be using the wrong date column\n"
            "   - Question format: 'Which date column should be used?' with options\n\n"
            "2) Data Freshness:\n"
            "   - Data is significantly stale (lag_days exceeds threshold)\n"
            "   - User's question implies they want current/recent data\n"
            "   - Question format: 'Data freshness information: Last available data is from YYYY-MM-DD, which is X days old. Do you want to proceed?'\n\n"
            "3) Filter Value Clarification:\n"
            "   - Vague filter values (e.g., 'high value', 'recent', 'active' without clear definition)\n"
            "   - Missing filter values that are needed for accurate results\n"
            "   - Ambiguous categorical values\n\n"
            "4) Join/Relationship Confirmation:\n"
            "   - Multiple possible join paths exist\n"
            "   - Ambiguity about which tables to join\n"
            "   - Missing join conditions that might affect results\n\n"
            "5) Aggregation Method:\n"
            "   - Question is ambiguous about aggregation (sum, count, average, max, min)\n"
            "   - Grouping requirements are unclear\n\n"
            "6) Output Format/Scope:\n"
            "   - Limit/row count preferences\n"
            "   - Column selection preferences\n"
            "   - Sorting preferences\n\n"
            "7) Any Other Clarification:\n"
            "   - Any ambiguity that could lead to incorrect or unexpected results\n"
            "   - Missing information needed to complete the query accurately\n\n"
            "CRITICAL RULES:\n"
            "- Ask questions ONLY when there is ACTUAL ambiguity or missing information that could affect results.\n"
            "- Do NOT ask questions when the intent is clear and unambiguous.\n"
            "- You can ask MULTIPLE follow-up questions if multiple ambiguities exist.\n"
            "- Return ALL relevant questions in the 'followup_questions' array.\n"
            "- Order questions logically (most critical first).\n"
            "- For date freshness questions, ALWAYS include the exact max available date and lag days from the provided metadata.\n"
            "- For date column questions, provide ALL available date columns as options.\n"
            "- CRITICAL: If the payload contains 'invalid_tables_in_sql' with table names, the SQL query uses non-existent tables. "
            "DO NOT ask questions about these invalid tables (e.g., 'table is empty', 'table has no data'). "
            "Instead, you may ask if the user meant a different table from the valid tables, or note that the SQL needs correction. "
            "NEVER reference invalid/non-existent tables in your questions.\n\n"
            "Output format:\n"
            "{\n"
            "  \"needs_followup\": true/false,\n"
            "  \"followup_questions\": [\n"
            "    {\n"
            "      \"id\": \"unique_question_id\",\n"
            "      \"question\": \"Clear, specific question text\",\n"
            "      \"type\": \"date_selection|confirmation|text_input|choice|number_input|etc\",\n"
            "      \"options\": [\"option1\", \"option2\", ...],  // Required for choice/date_selection types\n"
            "      \"required\": true/false,\n"
            "      \"default\": \"default_value\"  // Optional\n"
            "    }\n"
            "  ],\n"
            "  \"analysis\": \"Brief explanation of why these questions are needed\"\n"
            "}\n\n"
            "Question Types:\n"
            "- 'date_selection': User selects from date column options\n"
            "- 'confirmation': Yes/No question (e.g., data freshness)\n"
            "- 'text_input': User enters text (e.g., filter values)\n"
            "- 'choice': User selects from predefined options\n"
            "- 'number_input': User enters a number (e.g., threshold values)\n"
            "- Use other types as needed for specific clarifications\n\n"
            "Analysis Guidelines:\n"
            "1. Carefully read the user's question and the generated SQL query.\n"
            "2. Compare them to identify any mismatches, ambiguities, or missing information.\n"
            "3. Consider the schema context provided - are there multiple ways to interpret the question?\n"
            "4. Check if date/time information is ambiguous or if data freshness is a concern.\n"
            "5. Look for vague terms that need clarification (e.g., 'high value', 'recent', 'active').\n"
            "6. Identify if joins are missing or ambiguous.\n"
            "7. Determine if aggregation methods are unclear.\n"
            "8. Only ask questions when clarification is genuinely needed - don't over-question.\n\n"
            "Examples:\n"
            "Example 1 (Date ambiguity - ASK):\n"
            "Question: 'Show me all loans opened in the last 3 months'\n"
            "SQL uses: OPENING_DATE\n"
            "Available date columns: ['OPENING_DATE', 'INSERTED_ON', 'LAST_UPDATED_TS']\n"
            "→ ASK date_column question because 'opened' could mean OPENING_DATE or INSERTED_ON.\n\n"
            "Example 2 (Date ambiguity - DO NOT ASK):\n"
            "Question: 'Customers whose ReKYC due >6 months'\n"
            "SQL uses: RE_KYC_DUE_DATE (matches question keyword 'due')\n"
            "→ Do NOT ask - question explicitly mentions 'ReKYC due' which clearly maps to RE_KYC_DUE_DATE.\n\n"
            "Example 3 (Freshness - ASK):\n"
            "Question: 'Show me all current accounts'\n"
            "Freshness: {'table_name': {'max_value': '2025-01-15', 'lag_days': 5}}\n"
            "→ ASK freshness question because 'current' implies recent data, but data is 5 days old.\n\n"
            "Example 4 (Multiple ambiguities - ASK BOTH):\n"
            "Question: 'Show me all records from the last 6 months'\n"
            "SQL uses: INSERTED_ON\n"
            "Available date columns: ['OPENING_DATE', 'INSERTED_ON', 'LAST_UPDATED_TS']\n"
            "Freshness: {'table_name': {'max_value': '2025-01-15', 'lag_days': 5}}\n"
            "→ ASK BOTH date column selection AND freshness confirmation.\n\n"
            "Example 5 (No ambiguity - DO NOT ASK):\n"
            "Question: 'Show me loans with tenure less than 12 months'\n"
            "SQL uses: TENURE column correctly\n"
            "→ Do NOT ask - question is clear and SQL matches intent.\n\n"
            "Example 6 (Vague filter - ASK):\n"
            "Question: 'Show me high value loans'\n"
            "SQL uses: BALANCE > 1000000 (assumed threshold)\n"
            "→ ASK for clarification: 'What amount threshold should be used for high value loans?'\n"
            "Type: 'number_input' or 'choice' with options like ['> 1M', '> 5M', '> 10M']\n\n"
        )

    def _build_prompt(
        self,
        *,
        question: str,
        sql_query: str,
        tables: List[str],
        invalid_tables: List[str],
        table_date_cols: Dict[str, List[str]],
        table_freshness: Dict[str, Dict[str, Any]],
        date_cols_used: List[str],
        schema_context: Dict[str, Any],
        today: _dt.date,
    ) -> str:
        # Dynamically find date columns that match question keywords
        question_lower = question.lower()
        explicit_date_field = None
        
        # Look for date columns in the tables that match question keywords
        for table, date_cols in table_date_cols.items():
            for col in date_cols:
                col_lower = col.lower()
                if any(keyword in col_lower for keyword in question_lower.split() if len(keyword) > 3):
                    explicit_date_field = col
                    break
            if explicit_date_field:
                break
        
        # If no match found, check if SQL already uses a date column that seems relevant
        if not explicit_date_field and date_cols_used:
            explicit_date_field = date_cols_used[0]
        
        # Build comprehensive context for the LLM
        payload = {
            "user_question": question,
            "generated_sql_query": sql_query,
            "source_tables": tables,  # Valid tables only
            "invalid_tables_in_sql": invalid_tables,  # Tables that don't exist in database
            "schema_context": schema_context,  # Table schemas, columns, relationships
            "date_metadata": {
                "candidate_date_columns": table_date_cols,
                "date_columns_used_in_sql": date_cols_used,
                "explicit_date_field_mentioned": explicit_date_field,
            },
            "freshness_metadata": table_freshness,
            "today": str(today),
            "analysis_guidance": (
                "Analyze the user question and SQL query for ANY ambiguities, missing information, "
                "or clarifications needed. Consider:\n"
                "- Date/time ambiguities\n"
                "- Data freshness concerns\n"
                "- Vague filter values\n"
                "- Missing or ambiguous joins\n"
                "- Unclear aggregation methods\n"
                "- CRITICAL: If 'invalid_tables_in_sql' contains table names, the SQL query uses non-existent tables. "
                "You should NOT ask questions about these invalid tables (e.g., 'table is empty'). "
                "Instead, you may ask if the user meant a different table from the valid tables list, or flag that the SQL needs correction.\n"
                "- Any other aspects that could lead to incorrect or unexpected results\n"
            ),
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def _safe_json(self, txt: str) -> Any:
        try:
            return json.loads(txt)
        except Exception:
            m = re.search(r"\{[\s\S]*\}", txt or "")
            if not m:
                return None
            try:
                return json.loads(m.group(0))
            except Exception:
                return None

    def _extract_tables_from_sql(self, sql: str) -> List[str]:
        if not sql:
            return []
        cleaned = re.sub(r"```sql\s*|\s*```", "", sql, flags=re.IGNORECASE).strip()
        pattern = re.compile(
            r"\b(?:FROM|JOIN)\s+((?:\[[^\]]+\]|\w+)(?:\.(?:\[[^\]]+\]|\w+))?)",
            re.IGNORECASE,
        )
        found: List[str] = []
        for m in pattern.finditer(cleaned):
            ident = m.group(1).replace("[", "").replace("]", "")
            if "." in ident:
                schema, table = ident.split(".", 1)
                ident = table if schema.lower() == "dbo" else f"{schema}.{table}"
            found.append(ident)
        out: List[str] = []
        seen = set()
        for t in found:
            if t and t not in seen:
                seen.add(t)
                out.append(t)
        return out

    def _collect_date_metadata(
        self, db: Session, tables: List[str], today: _dt.date
    ) -> Tuple[Dict[str, List[str]], Dict[str, Dict[str, Any]]]:
        """
        Returns:
          - date columns per table (ordered)
          - freshness per table (best effort max(audit columns/other date columns))
        """
        # Get audit column names from config (generic, not hardcoded)
        audit_columns = [col.strip().upper() for col in settings.AUDIT_COLUMNS.split(",") if col.strip()]
        
        date_cols: Dict[str, List[str]] = {}
        freshness: Dict[str, Dict[str, Any]] = {}

        # Pull column names + data types from INFORMATION_SCHEMA
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
        rows = db.execute(cols_q, {"tables": list(tables)}).fetchall()
        by_table: Dict[str, List[Tuple[str, str]]] = {}
        for t, c, dt in rows:
            by_table.setdefault(t, []).append((c, (dt or "").lower()))

        date_types = {"date", "datetime", "datetime2", "smalldatetime", "datetimeoffset", "timestamp"}
        for t in tables:
            cols = by_table.get(t, [])
            candidates = []
            for c, dt in cols:
                name = (c or "").upper()
                if dt in date_types or name.endswith("_DT") or name.endswith("_DATE") or "DATE" in name:
                    candidates.append(c)
            # Sort with audit columns last (so user sees business dates first)
            candidates_sorted = sorted(
                set(candidates),
                key=lambda x: (x.upper() in audit_columns, x.upper()),
            )
            if candidates_sorted:
                date_cols[t] = candidates_sorted

            # Freshness: prefer audit columns (configurable), then fall back to business date columns
            preferred_cols = []
            for preferred in audit_columns:
                if any((c.upper() == preferred) for c, _ in cols):
                    preferred_cols.append(preferred)

            # Business date candidates (exclude audit columns)
            business_date_cols = [c for c in candidates_sorted if c.upper() not in audit_columns]

            def _try_max(colname: str):
                max_q = text(f"SELECT MAX([{colname}]) AS max_val FROM dbo.[{t}]")
                return db.execute(max_q).scalar()

            chosen_col = None
            max_val = None
            err = None
            try:
                for c in preferred_cols:
                    val = _try_max(c)
                    if val is not None:
                        chosen_col = c
                        max_val = val
                        break
                if max_val is None:
                    # Try business dates; pick the most recent max across them.
                    best = None
                    best_col = None
                    for c in business_date_cols[:8]:  # cap to avoid too many queries
                        val = _try_max(c)
                        if val is not None and (best is None or val > best):
                            best = val
                            best_col = c
                    if best is not None:
                        chosen_col = best_col
                        max_val = best
            except Exception as e:
                err = str(e)

            if chosen_col:
                lag_days = None
                try:
                    # max_val might be date/datetime; normalize to date for lag calc
                    if hasattr(max_val, "date"):
                        max_date = max_val.date()
                    else:
                        max_date = max_val
                    if isinstance(max_date, _dt.date):
                        lag_days = (today - max_date).days
                except Exception:
                    lag_days = None

                freshness[t] = {
                    "column": chosen_col,
                    "max_value": str(max_val) if max_val is not None else None,
                    "lag_days": lag_days,
                    "error": err,
                }
            elif preferred_cols or business_date_cols:
                # We had candidates but couldn't compute max
                freshness[t] = {
                    "column": (preferred_cols[0] if preferred_cols else business_date_cols[0]),
                    "max_value": None,
                    "lag_days": None,
                    "error": err or "no_non_null_max_value",
                }

        return date_cols, freshness

    def _extract_date_columns_used_in_sql(self, sql: str, table_date_cols: Dict[str, List[str]]) -> List[str]:
        """
        Best-effort: detect if any candidate date columns are referenced in WHERE/GROUP/ORDER.
        This is used to help the LLM avoid asking date-column questions for non-date queries.
        """
        if not sql:
            return []
        s = re.sub(r"\s+", " ", sql).upper()
        # Focus on predicate/order/group regions for stronger signal
        region = s
        m = re.search(r"\bWHERE\b|\bGROUP BY\b|\bORDER BY\b", s)
        if m:
            region = s[m.start():]

        candidates = set()
        for cols in table_date_cols.values():
            for c in cols:
                candidates.add(c.upper())

        used = []
        for c in candidates:
            # Match either [COL] or COL as a word
            if re.search(rf"\[\s*{re.escape(c)}\s*\]|\b{re.escape(c)}\b", region):
                used.append(c)

        used_sorted = sorted(set(used))
        return used_sorted

    def _get_schema_context(self, db: Session, tables: List[str]) -> Dict[str, Any]:
        """
        Get schema context for the tables used in the query.
        This helps the LLM identify ambiguities, missing joins, etc.
        """
        if not tables:
            return {}
        
        schema_info = {}
        
        try:
            # Get column information for each table
            cols_q = text(
                """
                SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = 'dbo'
                  AND TABLE_NAME IN :tables
                ORDER BY TABLE_NAME, ORDINAL_POSITION
                """
            ).bindparams(bindparam("tables", expanding=True))
            
            rows = db.execute(cols_q, {"tables": list(tables)}).fetchall()
            
            # Group by table
            by_table: Dict[str, List[Dict[str, str]]] = {}
            for t, c, dt, nullable, default in rows:
                if t not in by_table:
                    by_table[t] = []
                by_table[t].append({
                    "column": c,
                    "data_type": dt or "",
                    "nullable": nullable or "",
                    "default": default or "",
                })
            
            # Get primary key information
            pk_q = text(
                """
                SELECT TABLE_NAME, COLUMN_NAME
                FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = 'dbo'
                  AND TABLE_NAME IN :tables
                  AND CONSTRAINT_NAME IN (
                      SELECT CONSTRAINT_NAME
                      FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
                      WHERE CONSTRAINT_TYPE = 'PRIMARY KEY'
                        AND TABLE_SCHEMA = 'dbo'
                        AND TABLE_NAME IN :tables
                  )
                ORDER BY TABLE_NAME, ORDINAL_POSITION
                """
            ).bindparams(bindparam("tables", expanding=True))
            
            pk_rows = db.execute(pk_q, {"tables": list(tables)}).fetchall()
            pk_by_table: Dict[str, List[str]] = {}
            for t, c in pk_rows:
                if t not in pk_by_table:
                    pk_by_table[t] = []
                pk_by_table[t].append(c)
            
            # Get foreign key relationships (potential join paths)
            fk_q = text(
                """
                SELECT 
                    fk.TABLE_NAME AS FK_TABLE,
                    fk.COLUMN_NAME AS FK_COLUMN,
                    pk.TABLE_NAME AS PK_TABLE,
                    pk.COLUMN_NAME AS PK_COLUMN
                FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE fk
                    ON rc.CONSTRAINT_NAME = fk.CONSTRAINT_NAME
                    AND rc.CONSTRAINT_SCHEMA = fk.CONSTRAINT_SCHEMA
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE pk
                    ON rc.UNIQUE_CONSTRAINT_NAME = pk.CONSTRAINT_NAME
                    AND rc.UNIQUE_CONSTRAINT_SCHEMA = pk.CONSTRAINT_SCHEMA
                WHERE fk.TABLE_SCHEMA = 'dbo'
                  AND (fk.TABLE_NAME IN :tables OR pk.TABLE_NAME IN :tables)
                """
            ).bindparams(bindparam("tables", expanding=True))
            
            fk_rows = db.execute(fk_q, {"tables": list(tables)}).fetchall()
            relationships = []
            for fk_t, fk_c, pk_t, pk_c in fk_rows:
                relationships.append({
                    "from_table": fk_t,
                    "from_column": fk_c,
                    "to_table": pk_t,
                    "to_column": pk_c,
                })
            
            # Build schema context
            schema_info = {
                "tables": {},
                "relationships": relationships,
            }
            
            for table in tables:
                schema_info["tables"][table] = {
                    "columns": by_table.get(table, []),
                    "primary_keys": pk_by_table.get(table, []),
                }
        
        except Exception as e:
            _logger.warning(f"Could not fetch full schema context: {e}")
            # Return minimal context
            schema_info = {
                "tables": {t: {"columns": [], "primary_keys": []} for t in tables},
                "relationships": [],
            }
        
        return schema_info


