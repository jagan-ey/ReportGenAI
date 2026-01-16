"""
Chat API endpoints for Talk to Data functionality
"""
import logging
import re
import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from app.core.database import get_db, get_kb_db
from app.core.config import settings

# Setup dedicated logger for SQL validation debugging
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
_validator_logger.handlers.clear()  # Remove existing handlers
_validator_logger.addHandler(_validator_file_handler)
if settings.DEBUG:
    _validator_logger.addHandler(logging.StreamHandler())

_logger = logging.getLogger(__name__)


def _get_biu_spoc_message() -> str:
    """Generate BIU SPOC contact message for column/field errors"""
    return (
        f"\n\n📞 **Need Custom Query Support?**\n"
        f"If the requested column or field is not available in the current database schema, "
        f"please reach out to our BIU (Business Intelligence Unit) team to build a custom query:\n\n"
        f"**Contact Details:**\n"
        f"- **SPOC:** {settings.BIU_SPOC_NAME}\n"
        f"- **Email:** {settings.BIU_SPOC_EMAIL}\n"
        f"- **Phone:** {settings.BIU_SPOC_PHONE} ({settings.BIU_SPOC_EXTENSION})\n\n"
        f"The BIU team can help you create custom queries with the specific fields you need."
    )


def _check_semantic_mismatch(original_question: str, corrected_sql: str) -> bool:
    """
    Use LLM to check if the corrected SQL uses columns that don't semantically match the user's question.
    Returns True if there's a semantic mismatch (should show BIU SPOC message).
    
    This is generic and works for any domain - uses LLM to understand semantic meaning.
    """
    try:
        from langchain_openai import AzureChatOpenAI
        from langchain_core.messages import HumanMessage, SystemMessage
        import re
        
        # Extract column names from corrected SQL
        sql_upper = corrected_sql.upper()
        column_pattern = r'\b([A-Z_][A-Z0-9_]*)\b'
        sql_columns = re.findall(column_pattern, sql_upper)
        sql_columns_str = ', '.join(set(sql_columns))  # Remove duplicates
        
        if not sql_columns_str:
            return False
        
        # Initialize LLM (lazy, only when needed)
        llm = AzureChatOpenAI(
            azure_endpoint=settings.AZURE_ENDPOINT,
            api_key=settings.OPENAI_API_KEY,
            api_version=settings.AZURE_API_VERSION,
            deployment_name=settings.AZURE_DEPLOYMENT_NAME,
            temperature=0.0,
        )
        
        from app.services.prompt_loader import get_prompt_loader
        prompt_loader = get_prompt_loader()
        
        system_prompt = prompt_loader.get_prompt("semantic_analysis", "system_prompt")
        
        user_prompt = prompt_loader.get_prompt(
            "semantic_analysis",
            "user_prompt_template",
            original_question=original_question,
            sql_columns_str=sql_columns_str
        )
        
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ])
        
        answer = response.content.strip().upper() if hasattr(response, 'content') else str(response).strip().upper()
        
        # Check if LLM detected a mismatch
        is_mismatch = answer.startswith('NO')
        
        if is_mismatch:
            _logger.warning(f"⚠️ Semantic mismatch detected by LLM: Question asks for '{original_question}' but SQL uses columns: {sql_columns_str}")
        
        return is_mismatch
        
    except Exception as e:
        _logger.warning(f"⚠️ Could not check semantic mismatch using LLM: {e}. Assuming no mismatch.")
        # If LLM check fails, don't block - assume no mismatch
        return False


def _simplify_query_remove_unnecessary_join(sql: str, question: str) -> Optional[str]:
    """
    Simplify SQL by removing unnecessary joins when a table already has the needed columns.
    Generic - works for any tables, not hardcoded to specific table names.
    """
    sql_upper = sql.upper()
    
    # Extract tables from SQL
    from app.services.schema_helper import get_tables_from_sql
    tables = get_tables_from_sql(sql)
    
    # Only simplify if query has a JOIN (2+ tables)
    if len(tables) < 2:
        return None
    
    # Check if query returns 0 rows and has a JOIN - might be unnecessary join
    # This is a generic check - we'll let the validator/LLM handle specific cases
    if "JOIN" in sql_upper:
            _logger.info("Attempting to simplify query by removing unnecessary join...")
            
            # Extract SELECT columns
            select_match = re.search(r"SELECT\s+(.+?)\s+FROM", sql, re.IGNORECASE | re.DOTALL)
            if not select_match:
                return None
            
            # Get the first table (main table) from FROM clause
            from_match = re.search(r"FROM\s+(\w+)(?:\s+\w+)?", sql, re.IGNORECASE)
            if not from_match:
                return None
            
            main_table = from_match.group(1)
            
            select_clause = select_match.group(1)
            # Extract columns, keeping only those from main table
            select_cols = re.split(r",", select_clause)
            simplified_select = []
            for col in select_cols:
                col = col.strip()
                # Keep columns that don't reference joined tables (no table prefix or main table prefix)
                if not re.search(r"\w+\.", col, re.IGNORECASE) or re.search(rf"\b{main_table}\.", col, re.IGNORECASE):
                    # Remove table prefix if present
                    col = re.sub(rf"\b{main_table}\.", "", col, flags=re.IGNORECASE)
                    simplified_select.append(col)
            
            if not simplified_select:
                return None
            
            # Build simplified SQL using main table
            simplified_sql = f"SELECT {', '.join(simplified_select)} FROM {main_table}"
            
            # Extract WHERE conditions
            where_match = re.search(r"WHERE\s+(.+?)(?:\s+ORDER\s+BY|\s*$)", sql, re.IGNORECASE | re.DOTALL)
            if where_match:
                where_clause = where_match.group(1)
                
                # Split conditions by AND/OR
                conditions = re.split(r"\s+AND\s+", where_clause, flags=re.IGNORECASE)
                simplified_conditions = []
                for condition in conditions:
                    condition = condition.strip()
                    # Keep conditions that reference main table or have no table prefix
                    if not re.search(r"\w+\.", condition, re.IGNORECASE) or re.search(rf"\b{main_table}\.", condition, re.IGNORECASE):
                        # Remove table prefix if present
                        condition = re.sub(rf"\b{main_table}\.", "", condition, flags=re.IGNORECASE)
                        simplified_conditions.append(condition)
                
                if simplified_conditions:
                    simplified_sql += f" WHERE {' AND '.join(simplified_conditions)}"
            
            # Add ORDER BY if present
            order_match = re.search(r"ORDER\s+BY\s+(.+?)(?:\s*$)", sql, re.IGNORECASE | re.DOTALL)
            if order_match:
                order_clause = order_match.group(1).strip()
                # Remove table prefixes from ORDER BY
                order_clause = re.sub(rf"\b{main_table}\.", "", order_clause, flags=re.IGNORECASE)
                # Remove any other table references (joined tables)
                order_clause = re.sub(r"\b\w+\.", "", order_clause, flags=re.IGNORECASE)
                simplified_sql += f" ORDER BY {order_clause}"
            
            _logger.info(f"Simplified SQL generated: {simplified_sql}")
            return simplified_sql
    else:
        _logger.debug("Query does not have a JOIN - no simplification needed")
    
    return None


from app.services.sql_agent import SQLAgentService
from app.services.predefined_queries_db import get_predefined_query_by_key, get_all_predefined_queries
from app.services.orchestrator_agent import OrchestratorAgent
from app.services.sql_maker_agent import SQLMakerAgent
from app.services.followup_agent import FollowUpAgentService
from app.services.sql_validator_agent import SQLValidatorAgent
from app.services.insight_agent import InsightAgent
from app.core.config import settings

router = APIRouter()

# SQL Agent singleton (lazy initialization)
_sql_agent = None
_orchestrator = None
_sql_maker = None
_multi_agent = None
_followup_agent = None


def get_sql_agent():
    """Get or create SQL agent instance (lazy initialization)"""
    global _sql_agent
    if _sql_agent is None:
        # Build SQL Server connection string for LangChain
        # Use KB database for SQL agent (dimension tables are in KB DB)
        from app.core.database import get_kb_db_url
        db_url = get_kb_db_url()
        _sql_agent = SQLAgentService(db_url)
    return _sql_agent


def _get_orchestrator(db_url: str) -> OrchestratorAgent:
    global _orchestrator
    if _orchestrator is None or getattr(_orchestrator, "db_url", None) != db_url:
        _orchestrator = OrchestratorAgent(db_url)
    return _orchestrator


def _get_sql_maker(db_url: str) -> SQLMakerAgent:
    global _sql_maker
    if _sql_maker is None or getattr(_sql_maker, "db_url", None) != db_url:
        _sql_maker = SQLMakerAgent(db_url)
    return _sql_maker


def _get_multi_agent(db_url: str):
    global _multi_agent
    if _multi_agent is None or getattr(_multi_agent, "db_url", None) != db_url:
        from app.services.multi_agent_sql import MultiAgentSQLService
        _multi_agent = MultiAgentSQLService(db_url)
    return _multi_agent


def _get_followup_agent() -> FollowUpAgentService:
    global _followup_agent
    if _followup_agent is None:
        _followup_agent = FollowUpAgentService()
    return _followup_agent


_insight_agent = None


def _get_insight_agent() -> InsightAgent:
    global _insight_agent
    if _insight_agent is None:
        _insight_agent = InsightAgent()
    return _insight_agent


class ChatRequest(BaseModel):
    question: str
    query_key: Optional[str] = None  # If provided, directly use this predefined query (no matching needed)
    use_predefined: bool = True  # Use predefined queries for 100% accuracy
    previous_sql_query: Optional[str] = None  # Context for meta follow-ups like "from which table was this data?"
    followup_answers: Optional[dict] = None  # Follow-up answers from UI (if any)
    skip_followups: bool = False  # If true, do not ask follow-ups again
    mode: Optional[str] = "report"  # "conversation" or "report"


class ChatResponse(BaseModel):
    answer: str  # Brief textual summary
    sql_query: Optional[str] = None  # The actual SQL query
    data: Optional[list] = None  # Table data (list of dicts)
    row_count: Optional[int] = None  # Number of rows returned
    is_predefined: bool = False
    question_key: Optional[str] = None
    success: bool = True
    error: Optional[str] = None
    is_conversational: Optional[bool] = False  # True if this is a conversational response (no SQL)
    agent_used: Optional[str] = None  # e.g., predefined|orchestrator|sqlmaker|multi_agent|conversational
    route_reason: Optional[str] = None  # LLM router reason / debug hint
    needs_followup: Optional[bool] = False
    followup_questions: Optional[list] = None
    followup_analysis: Optional[str] = None
    insights: Optional[dict] = None  # Visualization recommendations and business insights


@router.post("/query", response_model=ChatResponse)
async def chat_query(
    request: ChatRequest, 
    db: Session = Depends(get_db),  # Main DB for predefined queries lookup
    kb_db: Session = Depends(get_kb_db)  # KB DB for SQL execution on dimension tables
):
    """
    Process a natural language query and return results
    """
    try:
        from app.core.database import get_kb_db_url
        db_url = get_kb_db_url()

        mode = (request.mode or "report").lower()
        if mode not in ("conversation", "report"):
            mode = "report"

        # If user is responding to follow-up questions, treat this as a confirmed report/data query.
        if request.followup_answers:
            # If user explicitly cancelled via any confirmation question
            for v in request.followup_answers.values():
                if isinstance(v, str) and v.lower().strip() == "no":
                    return ChatResponse(
                        answer="Cancelled. No query was executed.",
                        sql_query=None,
                        data=[],
                        row_count=0,
                        is_predefined=False,
                        success=True,
                        is_conversational=True,
                        agent_used="followup",
                        route_reason="user_cancelled",
                    )

            # Append follow-up answers to the question so SQLMaker can incorporate them.
            followup_suffix = " Follow-up answers: " + str(request.followup_answers)
            if hasattr(request, "model_copy"):
                request = request.model_copy(update={"question": request.question + followup_suffix, "skip_followups": True})
            else:
                request = request.copy(update={"question": request.question + followup_suffix, "skip_followups": True})

        # If user forces conversation mode, bypass SQL flows entirely
        if mode == "conversation":
            orchestrator = _get_orchestrator(db_url)
            result = orchestrator.conversational.handle_query(
                request.question,
                previous_sql_query=request.previous_sql_query,
            )
            return ChatResponse(
                answer=result.get("answer", "I'm here to help you with conversational questions."),
                sql_query=None,
                data=[],
                row_count=0,
                is_predefined=False,
                success=True,
                is_conversational=True,
                agent_used="conversational",
                route_reason="forced_conversation_mode",
            )

        # Orchestrator decides route: predefined vs report_sql vs conversational (only for report mode)
        orchestrator = _get_orchestrator(db_url)
        decision = orchestrator.decide(
            db=db,
            question=request.question,
            query_key=request.query_key,
            use_predefined=request.use_predefined,
            previous_sql_query=request.previous_sql_query,
        )

        # In report mode, if router thinks it's conversational, ask user to switch modes
        if decision.get("route") == "conversational" and mode == "report":
            return ChatResponse(
                answer="This looks like a conversational question. Please switch to Conversation mode for chat-style help. Report mode only generates SQL reports.",
                sql_query=None,
                data=[],
                row_count=0,
                is_predefined=False,
                success=False,
                is_conversational=True,
                agent_used="routing",
                route_reason="report_mode_conversational_reroute",
            )

        # 1) Predefined execution (direct SQLAlchemy)
        if decision.get("route") == "predefined":
            predefined_key = decision.get("predefined_key")
            predefined = get_predefined_query_by_key(db, predefined_key)
            if not predefined:
                return ChatResponse(
                    answer="Predefined query not found or inactive.",
                    sql_query=None,
                    data=[],
                    row_count=0,
                    is_predefined=False,
                    success=False,
                    error="Predefined query not found",
                    agent_used="predefined",
                    route_reason="matched_predefined",
                )

            try:
                from sqlalchemy import text
                # Predefined queries execute against KB database (dimension tables)
                result = kb_db.execute(text(predefined["sql"]))
                rows = result.fetchall()
                columns = result.keys()
                data = [dict(zip(columns, row)) for row in rows]
                row_count = len(data)
                answer = f"Found {row_count} record(s) matching the criteria." if row_count else "No records found matching the criteria."
                
                # Generate insights for predefined queries (only in report mode)
                insights = None
                if mode == "report" and len(data) > settings.INSIGHT_MIN_ROWS:
                    try:
                        _logger.info(f"Generating insights for predefined query with {len(data)} rows...")
                        insight_agent = _get_insight_agent()
                        insights = insight_agent.analyze(
                            data=data,
                            sql_query=predefined["sql"].strip(),
                            question=request.question,
                            schema_info=None
                        )
                        _logger.info(f"Insights generated successfully for predefined query")
                    except Exception as e:
                        _logger.error(f"Failed to generate insights for predefined query: {str(e)}")
                        insights = None
                
                return ChatResponse(
                    answer=answer,
                    sql_query=predefined["sql"].strip(),
                    data=data,
                    row_count=row_count,
                    is_predefined=True,
                    question_key=predefined_key,
                    success=True,
                    agent_used="predefined",
                    route_reason="matched_predefined",
                    insights=insights,
                )
            except Exception as e:
                return ChatResponse(
                    answer=f"Error executing predefined query: {str(e)}",
                    sql_query=predefined["sql"].strip(),
                    data=[],
                    row_count=0,
                    is_predefined=True,
                    question_key=predefined_key,
                    success=False,
                    error=str(e),
                    agent_used="predefined",
                    route_reason="matched_predefined",
                )

        # 2) Conversational (no SQL)
        if decision.get("route") == "conversational":
            result = orchestrator.conversational.handle_query(
                request.question,
                previous_sql_query=request.previous_sql_query,
            )
            return ChatResponse(
                answer=result.get("answer", "I'm here to help you query your data!"),
                sql_query=None,
                data=[],
                row_count=0,
                is_predefined=False,
                success=True,
                is_conversational=True,
                agent_used="conversational",
                route_reason=decision.get("reason"),
            )

        # 3) Report/Data query -> SQLMaker (LLM generates SQL) + execute
        _validator_logger.info("=" * 80)
        _validator_logger.info(f"🔍 NEW QUERY REQUEST: {request.question}")
        _validator_logger.info("=" * 80)
        
        sql_agent = get_sql_agent()
        sql_query = None

        # Try SQLMaker first
        _validator_logger.info("📝 Step 1: Calling SQLMaker Agent...")
        sql_maker = _get_sql_maker(db_url)
        maker_res = sql_maker.generate_sql(
            request.question,
            previous_sql_query=request.previous_sql_query  # Pass previous SQL query
        )
        used_agent = "sqlmaker"
        if maker_res.get("success"):
            sql_query = maker_res.get("sql_query")
            _validator_logger.info(f"✅ SQLMaker generated SQL (attempt {maker_res.get('attempt', 1)}):")
            _validator_logger.info(f"SQL: {sql_query}")
            if maker_res.get("attempt") == 2:
                used_agent = "sqlmaker_repair"
        else:
            _validator_logger.warning(f"❌ SQLMaker failed: {maker_res.get('error', 'Unknown error')}")
            # Fallback to existing multi-agent system for robustness
            multi_agent = _get_multi_agent(db_url)
            fallback_res = multi_agent.execute_query(request.question)
            sql_query = fallback_res.get("sql_query")
            used_agent = "multi_agent"
            if sql_query:
                _validator_logger.info(f"✅ Multi-agent fallback generated SQL: {sql_query}")

        if not sql_query:
            _validator_logger.error("❌ No SQL query generated by any agent")
            return ChatResponse(
                answer="I couldn't turn this into a report query. Please switch to Conversation mode for chat-style questions.",
                sql_query=None,
                data=[],
                row_count=0,
                is_predefined=False,
                success=False,
                error="Unable to generate SQL",
                is_conversational=True,
                agent_used=used_agent,
                route_reason="report_mode_no_sql_generated",
            )

        cleaned_sql = sql_agent._clean_sql_string(sql_query) if hasattr(sql_agent, "_clean_sql_string") else sql_query
        _validator_logger.info(f"📝 Step 2: Cleaned SQL: {cleaned_sql}")
        
        if not sql_agent.validate_sql(cleaned_sql):
            _validator_logger.error("❌ SQL validation failed - unsafe operations detected")
            return ChatResponse(
                answer="Generated SQL query contains unsafe operations and was blocked for security.",
                sql_query=cleaned_sql,
                data=[],
                row_count=0,
                is_predefined=False,
                success=False,
                error="Unsafe SQL query detected",
                agent_used=used_agent,
                route_reason=decision.get("reason"),
            )
        
        _validator_logger.info("✅ SQL passed safety validation")
        
        # SQL Validator Agent: Will be initialized only if SQLMaker's SQL fails during execution (fallback)
        # Do NOT call validator here - let SQLMaker's SQL execute first

        # FollowUp Agent (before execution)
        if not request.skip_followups:
            _validator_logger.info("📝 Step 3: Checking FollowUp Agent...")
            followup_agent = _get_followup_agent()
            # Use KB DB for followup analysis (dimension tables are in KB DB)
            followup = followup_agent.analyze(db=kb_db, question=request.question, sql_query=cleaned_sql)
            if followup.get("needs_followup"):
                _validator_logger.info("⚠️ FollowUp Agent requested clarification - returning early")
                return ChatResponse(
                    answer="I need a quick clarification before running this report.",
                    sql_query=cleaned_sql,
                    data=[],
                    row_count=0,
                    is_predefined=False,
                    success=True,
                    is_conversational=True,
                    agent_used="followup",
                    route_reason="date_or_freshness_clarification",
                    needs_followup=True,
                    followup_questions=followup.get("followup_questions", []),
                    followup_analysis=followup.get("analysis", ""),
                )
            _validator_logger.info("✅ FollowUp Agent - no clarification needed")

        _validator_logger.info("📝 Step 4: Executing SQL query...")
        try:
            from sqlalchemy import text
            # Execute SQL against KB database (dimension tables are in KB DB)
            db_result = kb_db.execute(text(cleaned_sql))
            _validator_logger.info("✅ SQL execution successful!")
            rows = db_result.fetchall()
            columns = db_result.keys()
            data = [dict(zip(columns, row)) for row in rows]
            row_count = len(data)

            # If query returns 0 rows and uses unnecessary joins, try simplified version
            if row_count == 0 and "JOIN" in cleaned_sql.upper():
                # Check if we can simplify by removing unnecessary join
                # Generic check - works for any tables
                    _logger.info("Query returned 0 rows with join, attempting simplified version...")
                    simplified_sql = _simplify_query_remove_unnecessary_join(cleaned_sql, request.question)
                    if simplified_sql and simplified_sql != cleaned_sql:
                        # Validate simplified SQL is safe
                        if sql_agent.validate_sql(simplified_sql):
                            try:
                                _logger.info(f"Trying simplified SQL: {simplified_sql}")
                                db_result = kb_db.execute(text(simplified_sql))
                                rows = db_result.fetchall()
                                columns = db_result.keys()
                                data = [dict(zip(columns, row)) for row in rows]    
                                row_count = len(data)
                                if row_count > 0:
                                    cleaned_sql = simplified_sql
                                    used_agent = f"{used_agent}"
                                    _logger.info(f"✅ Simplified query returned {row_count} rows")
                                else:
                                    _logger.warning(f"Simplified query also returned 0 rows")
                            except Exception as e:
                                _logger.error(f"Simplified query execution failed: {e}", exc_info=True)
                        else:
                            _logger.warning(f"Simplified SQL failed safety validation")
                    else:
                        _logger.warning(f"Could not generate simplified SQL. simplified_sql={simplified_sql is not None}, different={simplified_sql != cleaned_sql if simplified_sql else False}")
                        # Note: If execution fails, validator will be called in exception handler

            ql = request.question.lower()
            if row_count == 0:
                answer_text = "No records found matching your query."
            elif "how many" in ql or "count" in ql:
                answer_text = f"Found {row_count} record(s)."
            else:
                answer_text = f"Found {row_count} record(s)."

            # Generate insights if row count exceeds threshold (only in report mode)
            insights = None
            if mode == "report" and len(data) > settings.INSIGHT_MIN_ROWS:
                try:
                    _logger.info(f"Generating insights for {len(data)} rows...")
                    insight_agent = _get_insight_agent()
                    insights = insight_agent.analyze(
                        data=data,
                        sql_query=cleaned_sql,
                        question=request.question,
                        schema_info=None
                    )
                    _logger.info(f"Insights generated successfully")
                except Exception as e:
                    _logger.error(f"Failed to generate insights: {str(e)}")
                    insights = None
            else:
                _logger.debug(f"Skipping insight generation: mode={mode}, row_count={row_count}, threshold={settings.INSIGHT_MIN_ROWS}")

            return ChatResponse(
                answer=answer_text,
                sql_query=cleaned_sql,
                data=data,
                row_count=row_count,
                is_predefined=False,
                success=True,
                agent_used=used_agent,
                route_reason=decision.get("reason"),
                insights=insights,
            )
        except Exception as e:
            error_str = str(e)
            _validator_logger.error("=" * 80)
            _validator_logger.error(f"❌ SQL EXECUTION FAILED!")
            _validator_logger.error(f"Error: {error_str}")
            _validator_logger.error("=" * 80)
            _logger.error(f"SQL execution error caught: {error_str}")
            
            # Check if error is due to invalid column names, table names, or syntax errors
            # 42S22 = Invalid column name, 42S02 = Invalid object name (table/view)
            is_column_error = "Invalid column" in error_str or "column" in error_str.lower() or "42S22" in error_str
            is_table_error = "Invalid object name" in error_str or "table" in error_str.lower() or "42S02" in error_str
            is_syntax_error = "syntax" in error_str.lower() or "incorrect syntax" in error_str.lower()
            
            _validator_logger.info(f"🔍 Error Classification:")
            _validator_logger.info(f"  - Column Error: {is_column_error}")
            _validator_logger.info(f"  - Table Error: {is_table_error}")
            _validator_logger.info(f"  - Syntax Error: {is_syntax_error}")
            _logger.info(f"Error classification - Column: {is_column_error}, Table: {is_table_error}, Syntax: {is_syntax_error}")
            
            # SQL Validator Agent: Use as fallback when SQLMaker's SQL fails during execution
            # ALWAYS attempt correction for ANY SQL execution error (not just column/table/syntax)
            # This ensures validator handles all SQLMaker errors
            should_use_validator = is_column_error or is_table_error or is_syntax_error
            
            # Also check for other common SQL errors that should trigger validator
            if not should_use_validator:
                # Check for other SQL errors that might need correction
                other_sql_errors = [
                    "Invalid object", "object name", "does not exist", 
                    "ambiguous", "cannot resolve", "unknown", "not found"
                ]
                for error_keyword in other_sql_errors:
                    if error_keyword.lower() in error_str.lower():
                        should_use_validator = True
                        _validator_logger.info(f"✅ Detected other SQL error keyword '{error_keyword}', will use validator")
                        _logger.info(f"Detected other SQL error keyword '{error_keyword}', will use validator")
                        break
            
            _validator_logger.info(f"📝 Step 5: Should use validator? {should_use_validator}")
            
            if should_use_validator:
                try:
                    _validator_logger.info("=" * 80)
                    _validator_logger.info("🔧 CALLING SQL VALIDATOR AGENT")
                    _validator_logger.info("=" * 80)
                    _logger.info(f"SQLMaker query failed. Attempting correction using SQL Validator Agent: {error_str}")
                    
                    # Initialize validator (lazy - only when needed as fallback)
                    _validator_logger.info("📝 Initializing SQL Validator Agent...")
                    # Use KB DB for validator (dimension tables are in KB DB)
                    validator = SQLValidatorAgent(db=kb_db)
                    
                    # Get schema info directly from database instead of sql_agent (which may not be initialized)
                    # The validator can get schema info itself, but we can provide it if available
                    schema_info = None
                    try:
                        # Try to get schema info from sql_agent if it's already initialized
                        if hasattr(sql_agent, "get_schema_info") and hasattr(sql_agent, "_schema_cache") and sql_agent._schema_cache:
                            schema_info = sql_agent._schema_cache
                            _validator_logger.info(f"✅ Using cached schema info from sql_agent (length: {len(schema_info)})")
                        else:
                            _validator_logger.info("⚠️ Schema info not available from sql_agent - validator will get it directly from database")
                    except Exception as schema_error:
                        _validator_logger.warning(f"⚠️ Could not get schema info from sql_agent: {schema_error}. Validator will get it directly.")
                    
                    _validator_logger.info(f"✅ Validator initialized. Schema info provided: {schema_info is not None}")
                    
                    # Try to correct the SQL
                    _validator_logger.info(f"📝 Calling validator.validate_and_correct()...")
                    _validator_logger.info(f"  - Original SQL: {cleaned_sql}")
                    _validator_logger.info(f"  - Original Question: {request.question}")
                    _validator_logger.info(f"  - Error Message: {error_str[:500]}")
                    
                    correction_result = validator.validate_and_correct(
                        sql_query=cleaned_sql,
                        original_question=request.question,
                        schema_info=schema_info,
                        error_message=error_str
                    )
                    
                    _validator_logger.info(f"📝 Validator returned:")
                    _validator_logger.info(f"  - Valid: {correction_result.get('valid')}")
                    _validator_logger.info(f"  - Has corrected_sql: {bool(correction_result.get('corrected_sql'))}")
                    _validator_logger.info(f"  - Error: {correction_result.get('error')}")
                    _validator_logger.info(f"  - Attempts: {correction_result.get('attempts')}")
                
                    if correction_result.get("corrected_sql"):
                        corrected_sql = correction_result["corrected_sql"]
                        _validator_logger.info(f"✅ Validator provided corrected SQL:")
                        _validator_logger.info(f"SQL: {corrected_sql}")
                        
                        # Check for semantic mismatch - if corrected SQL doesn't match user's intent
                        _validator_logger.info("📝 Checking for semantic mismatch between question and corrected SQL...")
                        if _check_semantic_mismatch(request.question, corrected_sql):
                            _validator_logger.warning("⚠️ Semantic mismatch detected - corrected SQL doesn't match user's intent")
                            _logger.warning("Semantic mismatch: Validator corrected SQL but it doesn't match user's question")
                            # Don't use the corrected SQL - fall through to show BIU SPOC message
                        else:
                            _validator_logger.info("✅ No semantic mismatch detected")
                            # Validate corrected SQL is safe
                            _validator_logger.info("📝 Validating corrected SQL for safety...")
                            if sql_agent.validate_sql(corrected_sql):
                                _validator_logger.info("✅ Corrected SQL passed safety validation")
                                try:
                                    # Retry with corrected SQL
                                    _validator_logger.info("📝 Retrying execution with corrected SQL...")
                                    _logger.info(f"✅ Validator provided corrected SQL. Retrying execution...")
                                    db_result = kb_db.execute(text(corrected_sql))
                                    _validator_logger.info("✅ Corrected SQL execution successful!")
                                    rows = db_result.fetchall()
                                    columns = db_result.keys()
                                    data = [dict(zip(columns, row)) for row in rows]
                                    row_count = len(data)
                                    
                                    ql = request.question.lower()
                                    if row_count == 0:
                                        answer_text = "No records found matching your query."
                                    elif "how many" in ql or "count" in ql:
                                        answer_text = f"Found {row_count} record(s)."
                                    else:
                                        answer_text = f"Found {row_count} record(s)."
                                    
                                    # Generate insights for validator-corrected queries (only in report mode)
                                    insights = None
                                    if mode == "report" and len(data) > settings.INSIGHT_MIN_ROWS:
                                        try:
                                            _logger.info(f"Generating insights for validator-corrected query with {len(data)} rows...")
                                            insight_agent = _get_insight_agent()
                                            insights = insight_agent.analyze(
                                                data=data,
                                                sql_query=corrected_sql,
                                                question=request.question,
                                                schema_info=None
                                            )
                                            _logger.info(f"Insights generated successfully for validator-corrected query")
                                        except Exception as e:
                                            _logger.error(f"Failed to generate insights for validator-corrected query: {str(e)}")
                                            insights = None
                                    
                                    return ChatResponse(
                                        answer=answer_text,
                                        sql_query=corrected_sql,
                                        data=data,
                                        row_count=row_count,
                                        is_predefined=False,
                                        success=True,
                                        agent_used=f"{used_agent}_validator_corrected",
                                        route_reason=decision.get("reason"),
                                        insights=insights,
                                    )
                                except Exception as retry_error:
                                    _validator_logger.error(f"❌ Corrected SQL execution also failed: {retry_error}")
                                    _logger.error(f"Validator-corrected SQL also failed: {retry_error}")
                                    # Fall through to return original error
                            else:
                                _validator_logger.warning("⚠️ Validator-corrected SQL contains unsafe operations")
                                _logger.warning("Validator-corrected SQL contains unsafe operations")
                    else:
                        _validator_logger.warning("⚠️ Validator could not generate corrected SQL")
                        _logger.warning("Validator could not generate corrected SQL")
                except Exception as validator_error:
                    _validator_logger.error(f"❌ Exception in validator correction: {validator_error}", exc_info=True)
                    _logger.error(f"Error in validator correction: {validator_error}", exc_info=True)
                    # Even if validator fails, log it but continue to return error
            else:
                _validator_logger.warning(f"⚠️ SQL error detected but validator NOT triggered")
                _validator_logger.warning(f"Error: {error_str[:200]}")
                _logger.warning(f"SQL error detected but validator not triggered. Error: {error_str[:200]}")
            
            # If correction failed or validator wasn't triggered, return error
            # Check if it's still column/field related for BIU SPOC message
            is_column_error = "column" in error_str.lower() or "field" in error_str.lower() or "42S22" in error_str
            is_table_error_final = "Invalid object name" in error_str or "table" in error_str.lower() or "42S02" in error_str
            
            answer_text = f"Error executing SQL query: {error_str}"
            if is_column_error or is_table_error_final:
                answer_text += _get_biu_spoc_message()
            
            return ChatResponse(
                answer=answer_text,
                sql_query=cleaned_sql,
                data=[],
                row_count=0,
                is_predefined=False,
                success=False,
                error=error_str,
                agent_used=used_agent,
                route_reason=decision.get("reason"),
            )
    
    except Exception as e:
        # Catch any other unexpected errors
        return ChatResponse(
            answer=f"Unexpected error: {str(e)}",  # Brief textual summary
            sql_query=None,  # Always include SQL query field
            data=[],  # Always a list, not None
            row_count=0,  # Always an integer
            is_predefined=False,
            success=False,
            error=str(e)
        )


@router.get("/schema")
async def get_schema():
    """Get database schema information"""
    try:
        agent = get_sql_agent()
        schema_info = agent.get_schema_info()
        return {"schema": schema_info}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/test-llm")
async def test_llm():
    """Test Azure OpenAI connection"""
    try:
        from langchain_openai import AzureChatOpenAI
        from app.core.config import settings
        
        llm = AzureChatOpenAI(
            azure_endpoint=settings.AZURE_ENDPOINT,
            api_key=settings.OPENAI_API_KEY,
            api_version=settings.AZURE_API_VERSION,
            deployment_name=settings.AZURE_DEPLOYMENT_NAME,
            temperature=0.0
        )
        
        # Simple test
        response = llm.invoke("Say 'Hello' in one word")
        
        return {
            "status": "success",
            "message": "Azure OpenAI is working",
            "test_response": response.content if hasattr(response, 'content') else str(response),
            "endpoint": settings.AZURE_ENDPOINT,
            "deployment": settings.AZURE_DEPLOYMENT_NAME
        }
    except ImportError as e:
        return {
            "status": "error",
            "message": "LangChain modules not available",
            "error": str(e),
            "solution": "Run: pip install -r requirements.txt"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": "Azure OpenAI connection failed",
            "error": str(e),
            "check": [
                "1. Verify Azure endpoint is correct",
                "2. Check API key is valid",
                "3. Ensure deployment name matches your Azure OpenAI deployment",
                "4. Check network connectivity"
            ]
        }


@router.get("/predefined")
async def list_predefined_queries(db: Session = Depends(get_db)):
    """List all predefined queries from database"""
    try:
        queries = get_all_predefined_queries(db)
        return {
            "queries": [
                {
                    "key": q["key"],
                    "question": q["question"],
                    "description": q["description"]
                }
                for q in queries
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading queries: {str(e)}")
