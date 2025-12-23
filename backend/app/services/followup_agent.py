"""
FollowUp Agent (LLM)

Triggered after SQL is generated (but before execution) to decide if clarification is needed:
1) Date dimension selection: if source tables contain multiple date columns and the query doesn't specify which to use.
2) Data freshness confirmation: if tables indicate data is only updated up to an older date than "today".

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

        table_date_cols, table_freshness = self._collect_date_metadata(db, tables, today=today)
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

        # If we can't compute metadata, do not block execution.
        if not table_date_cols and not filtered_freshness:
            return {"needs_followup": False, "followup_questions": [], "analysis": "No date metadata available."}

        # If LLM not available, do not block (avoid hardcoding behavior).
        self._ensure_initialized()
        if not self._llm:
            return {"needs_followup": False, "followup_questions": [], "analysis": "Follow-up agent unavailable."}

        prompt = self._build_prompt(
            question=question,
            sql_query=sql_query,
            tables=tables,
            table_date_cols=table_date_cols,
            table_freshness=filtered_freshness,  # Use filtered freshness
            date_cols_used=date_cols_used,
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
            "You are a follow-up question generator for a banking data assistant.\n"
            "Your job is to decide whether we need to ask the user clarifying questions BEFORE executing SQL.\n"
            "You must output ONLY valid JSON.\n\n"
            "When to ask follow-ups:\n"
            "1) Date dimension ambiguity: If the user's question is time/date-based AND there is ACTUAL ambiguity about which date column to use. Only ask if:\n"
            "   a) The question is vague (e.g., 'opened recently', 'in the last 3 months' without specifying which date field)\n"
            "   b) Multiple date columns exist AND the question doesn't explicitly mention a specific date field\n"
            "   c) The SQL might be using the wrong date column\n"
            "   DO NOT ask if:\n"
            "   - The question explicitly mentions a specific date field that matches a column name in the schema\n"
            "   - The SQL already uses the correct, unambiguous date column that matches the question's intent\n"
            "2) Data freshness risk: If the user's question is time/date-based (e.g., 'in the last 6 months', 'opened recently', 'current', 'latest') AND the freshness metadata shows lag_days exceeds the threshold (data is significantly stale), you MUST ask a freshness confirmation question. Include the exact max available date and lag days in the question.\n\n"
            "IMPORTANT:\n"
            "- Ask date-column question ONLY when: user question is date-based AND there is ACTUAL ambiguity (question doesn't specify which date field, or SQL might be using wrong column).\n"
            "- Do NOT ask date-column question when:\n"
            "  * User question is NOT date-based (e.g., tenure, amount, scheme filters only)\n"
            "  * User question explicitly mentions a specific date field that matches a column name AND SQL uses the correct matching column\n"
            "  * The question clearly maps to one specific date column based on keyword matching with column names\n"
            "- Ask freshness question when: user question is time/date-based (contains phrases like 'in the last X months', 'opened', 'recent', 'current', 'latest', 'as of') AND freshness metadata is provided (only tables with lag_days exceeding threshold are included).\n"
            "- If freshness metadata is empty or not provided, do NOT ask freshness question (data is fresh or within acceptable threshold).\n"
            "- If you raise a freshness warning, ALWAYS include the exact max available date and the lag vs today (from the provided freshness metadata) in the question text.\n\n"
            "Output format:\n"
            "{\n"
            "  \"needs_followup\": true/false,\n"
            "  \"followup_questions\": [\n"
            "    {\n"
            "      \"id\": \"date_column\",\n"
            "      \"question\": \"Which date column should be used?\",\n"
            "      \"type\": \"date_selection\",\n"
            "      \"options\": [\"col1\", \"col2\", \"Entire available range\"],\n"
            "      \"required\": true\n"
            "    }\n"
            "  ],\n"
            "  \"analysis\": \"short explanation\"\n"
            "}\n\n"
            "Few-shot examples:\n"
            "Example 1 (Ambiguous date question - ASK):\n"
            "Question: 'Show me all loans opened in the last 3 months'\n"
            "SQL uses: OPENING_DATE\n"
            "Available columns: ['OPENING_DATE', 'INSERTED_ON', 'LAST_UPDATED_TS'] (example columns)\n"
            "→ ASK date_column question because question is vague ('opened' could mean OPENING_DATE or INSERTED_ON) and multiple columns exist.\n\n"
            "Example 1b (Explicit date field - DO NOT ASK):\n"
            "Question: 'Customers whose ReKYC due >6 months'\n"
            "SQL uses: DUE_DATE (matches question keyword 'due')\n"
            "Available columns: ['DUE_DATE', 'INSERTED_ON', 'LAST_UPDATED_TS'] (example - use actual columns from schema)\n"
            "→ Do NOT ask date_column question because question explicitly mentions a keyword that matches the column name, and SQL already uses it correctly.\n\n"
            "Example 1c (Explicit date field - DO NOT ASK):\n"
            "Question: 'Show me accounts opened in the last 6 months'\n"
            "SQL uses: OPENING_DATE\n"
            "Available columns: ['OPENING_DATE', 'INSERTED_ON', 'LAST_UPDATED_TS'] (example columns)\n"
            "→ Do NOT ask date_column question because 'accounts opened' clearly refers to OPENING_DATE (account opening date), and SQL already uses it correctly.\n\n"
            "Example 2 (Non-date question):\n"
            "Question: 'Show me loans with tenure less than 12 months'\n"
            "SQL uses: TENURE (not a date column)\n"
            "Available columns: ['OPENING_DATE', 'INSERTED_ON', 'LAST_UPDATED_TS'] (example columns)\n"
            "→ Do NOT ask date_column question because user question is NOT date-based.\n\n"
            "Example 3 (Freshness warning - CRITICAL):\n"
            "Question: 'Show me all accounts opened in the last 6 months'\n"
            "Freshness metadata: {'table_name': {'max_value': '2025-01-15 10:30:00', 'lag_days': 5, 'column': 'audit_column'}}\n"
            "→ MUST ASK freshness question because:\n"
            "  1. Question is time-based ('in the last 6 months')\n"
            "  2. lag_days = 5 (exceeds threshold, data is significantly stale)\n"
            "  3. Freshness metadata is provided (only tables exceeding threshold are included)\n"
            "Question format: 'Data freshness information: Last available data is from 2025-01-15, which is 5 days old. Do you want to proceed?'\n"
            "Type: 'confirmation'\n"
            "ID: 'data_freshness'\n\n"
            "Example 4 (Both date column AND freshness - but only if ambiguous):\n"
            "Question: 'Show me all accounts opened in the last 6 months'\n"
            "SQL uses: OPENING_DATE\n"
            "Available columns: ['OPENING_DATE', 'INSERTED_ON', 'LAST_UPDATED_TS'] (example columns)\n"
            "Freshness metadata: {'table_name': {'max_value': '2025-01-15', 'lag_days': 5}}\n"
            "→ ASK ONLY freshness (NOT date column) because:\n"
            "  1. Question mentions 'accounts opened' which clearly maps to OPENING_DATE, and SQL uses it correctly\n"
            "  2. No ambiguity exists - DO NOT ask date column question\n"
            "  3. Freshness confirmation (lag_days = 5 > 0) - ASK this\n\n"
            "Example 4b (Ambiguous date + freshness - ASK BOTH):\n"
            "Question: 'Show me all records from the last 6 months'\n"
            "SQL uses: INSERTED_ON\n"
            "Available columns: ['OPENING_DATE', 'INSERTED_ON', 'LAST_UPDATED_TS'] (example columns)\n"
            "Freshness metadata: {'table_name': {'max_value': '2025-01-15', 'lag_days': 5}}\n"
            "→ ASK BOTH:\n"
            "  1. Date column selection (question is vague - 'records' doesn't specify which date field)\n"
            "  2. Freshness confirmation (lag_days = 5 > 0)\n\n"
            "Example 5 (Freshness below threshold):\n"
            "Question: 'Show me all accounts opened in the last 6 months'\n"
            "Freshness metadata: {} (empty - lag_days = 1 is below threshold of 3 days)\n"
            "→ Do NOT ask freshness question because freshness metadata is empty (data is within acceptable threshold).\n\n"
            "Example 6 (Freshness with no lag):\n"
            "Question: 'Show me all accounts opened in the last 6 months'\n"
            "Freshness metadata: {} (empty - lag_days = 0 or None)\n"
            "→ Do NOT ask freshness question because freshness metadata is empty (data is current).\n"
        )

    def _build_prompt(
        self,
        *,
        question: str,
        sql_query: str,
        tables: List[str],
        table_date_cols: Dict[str, List[str]],
        table_freshness: Dict[str, Dict[str, Any]],
        date_cols_used: List[str],
        today: _dt.date,
    ) -> str:
        # Dynamically find date columns that match question keywords
        # Instead of hardcoded mappings, we'll use the actual date columns from tables
        question_lower = question.lower()
        explicit_date_field = None
        
        # Look for date columns in the tables that match question keywords
        # This is generic - works for any date columns, not just hardcoded ones
        for table, date_cols in table_date_cols.items():
            for col in date_cols:
                col_lower = col.lower()
                # Check if column name contains keywords from question
                # Generic matching: if question mentions something that matches column name pattern
                if any(keyword in col_lower for keyword in question_lower.split() if len(keyword) > 3):
                    # Found a potential match - use it
                    explicit_date_field = col
                    break
            if explicit_date_field:
                break
        
        # If no match found, check if SQL already uses a date column that seems relevant
        if not explicit_date_field and date_cols_used:
            # Use the first date column that's already in the SQL
            explicit_date_field = date_cols_used[0]
        
        payload = {
            "question": question,
            "sql_query": sql_query,
            "source_tables": tables,
            "candidate_date_columns": table_date_cols,
            "date_columns_used_in_sql": date_cols_used,
            "freshness": table_freshness,
            "today": str(today),
            "explicit_date_field_mentioned": explicit_date_field,  # Add this hint
            "guidance": (
                "If the question explicitly mentions a specific date field that matches a column name "
                "AND the SQL already uses that correct column, "
                "DO NOT ask for date column selection - there is no ambiguity."
            ) if explicit_date_field else None,
        }
        return json.dumps(payload, ensure_ascii=False)

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


