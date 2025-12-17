"""
Chat API endpoints for Talk to Data functionality
"""
import logging
import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings

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


def _simplify_query_remove_unnecessary_join(sql: str, question: str) -> Optional[str]:
    """
    Simplify SQL by removing unnecessary joins with caselite_loan_applications
    when super_loan_account_dim.SCHEME is already being used.
    """
    sql_upper = sql.upper()
    
    # Only simplify if query uses super_loan_account_dim.SCHEME and joins with caselite_loan_applications
    if "SUPER_LOAN_ACCOUNT_DIM" in sql_upper and "CASELITE_LOAN_APPLICATIONS" in sql_upper:
        # Check if SCHEME is used (case-insensitive)
        if re.search(r"(SLA|SUPER_LOAN_ACCOUNT_DIM)\.SCHEME", sql_upper):
            _logger.info("Attempting to simplify query by removing unnecessary join...")
            
            # Extract SELECT columns (remove cla references)
            select_match = re.search(r"SELECT\s+(.+?)\s+FROM", sql, re.IGNORECASE | re.DOTALL)
            if not select_match:
                return None
            
            select_clause = select_match.group(1)
            # Remove cla references from SELECT
            select_cols = re.split(r",", select_clause)
            simplified_select = []
            for col in select_cols:
                col = col.strip()
                # Skip columns from caselite_loan_applications
                if re.search(r"\b(CLA|CASELITE_LOAN_APPLICATIONS)\.", col, re.IGNORECASE):
                    continue
                # Replace sla alias or remove it
                col = re.sub(r"\bSLA\.", "", col, flags=re.IGNORECASE)
                simplified_select.append(col)
            
            if not simplified_select:
                return None
            
            # Build simplified SQL
            simplified_sql = f"SELECT {', '.join(simplified_select)} FROM super_loan_account_dim"
            
            # Extract WHERE conditions
            where_match = re.search(r"WHERE\s+(.+?)(?:\s+ORDER\s+BY|\s*$)", sql, re.IGNORECASE | re.DOTALL)
            if where_match:
                where_clause = where_match.group(1)
                
                # Split conditions by AND/OR
                conditions = re.split(r"\s+AND\s+", where_clause, flags=re.IGNORECASE)
                simplified_conditions = []
                for condition in conditions:
                    condition = condition.strip()
                    # Skip conditions referencing caselite_loan_applications (cla)
                    if re.search(r"\b(CLA|CASELITE_LOAN_APPLICATIONS)\.", condition, re.IGNORECASE):
                        continue
                    # Replace sla alias or remove it
                    condition = re.sub(r"\bSLA\.", "", condition, flags=re.IGNORECASE)
                    simplified_conditions.append(condition)
                
                if simplified_conditions:
                    simplified_sql += f" WHERE {' AND '.join(simplified_conditions)}"
            
            # Add ORDER BY if present
            order_match = re.search(r"ORDER\s+BY\s+(.+?)(?:\s*$)", sql, re.IGNORECASE | re.DOTALL)
            if order_match:
                order_clause = order_match.group(1).strip()
                # Remove cla references from ORDER BY
                order_clause = re.sub(r"\b(CLA|CASELITE_LOAN_APPLICATIONS)\.", "", order_clause, flags=re.IGNORECASE)
                order_clause = re.sub(r"\bSLA\.", "", order_clause, flags=re.IGNORECASE)
                simplified_sql += f" ORDER BY {order_clause}"
            
            _logger.info(f"Simplified SQL generated: {simplified_sql}")
            return simplified_sql
        else:
            _logger.debug("Query uses SCHEME but simplification conditions not met")
    else:
        _logger.debug("Query doesn't match simplification criteria")
    
    return None


from app.services.sql_agent import SQLAgentService
from app.services.predefined_queries_db import get_predefined_query_by_key, get_all_predefined_queries
from app.services.orchestrator_agent import OrchestratorAgent
from app.services.sql_maker_agent import SQLMakerAgent
from app.services.followup_agent import FollowUpAgentService
from app.services.sql_validator_agent import SQLValidatorAgent
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
        from urllib.parse import quote_plus
        db_url = (
            f"mssql+pyodbc://{settings.DB_USERNAME}:{quote_plus(settings.DB_PASSWORD)}"
            f"@{settings.DB_SERVER}/{settings.DB_NAME}"
            f"?driver={quote_plus(settings.DB_DRIVER)}"
            f"&TrustServerCertificate=yes"
        )
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


class ChatRequest(BaseModel):
    question: str
    query_key: Optional[str] = None  # If provided, directly use this predefined query (no matching needed)
    use_predefined: bool = True  # Use predefined queries for 100% accuracy
    previous_sql_query: Optional[str] = None  # Context for meta follow-ups like "from which table was this data?"
    followup_answers: Optional[dict] = None  # Follow-up answers from UI (if any)
    skip_followups: bool = False  # If true, do not ask follow-ups again


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


@router.post("/query", response_model=ChatResponse)
async def chat_query(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Process a natural language query and return results
    """
    try:
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

        # Orchestrator decides route: predefined vs report_sql vs conversational
        from app.core.database import get_db_url
        db_url = get_db_url()
        orchestrator = _get_orchestrator(db_url)
        decision = orchestrator.decide(
            db=db,
            question=request.question,
            query_key=request.query_key,
            use_predefined=request.use_predefined,
            previous_sql_query=request.previous_sql_query,
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
                result = db.execute(text(predefined["sql"]))
                rows = result.fetchall()
                columns = result.keys()
                data = [dict(zip(columns, row)) for row in rows]
                row_count = len(data)
                answer = f"Found {row_count} record(s) matching the criteria." if row_count else "No records found matching the criteria."
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
        sql_agent = get_sql_agent()
        sql_query = None

        # Try SQLMaker first
        sql_maker = _get_sql_maker(db_url)
        maker_res = sql_maker.generate_sql(
            request.question,
            previous_sql_query=request.previous_sql_query  # Pass previous SQL query
        )
        used_agent = "sqlmaker"
        if maker_res.get("success"):
            sql_query = maker_res.get("sql_query")
            if maker_res.get("attempt") == 2:
                used_agent = "sqlmaker_repair"
        else:
            # Fallback to existing multi-agent system for robustness
            multi_agent = _get_multi_agent(db_url)
            fallback_res = multi_agent.execute_query(request.question)
            sql_query = fallback_res.get("sql_query")
            used_agent = "multi_agent"

        if not sql_query:
            return ChatResponse(
                answer="Error: Unable to generate SQL query. Please try rephrasing your question or use a predefined query.",
                sql_query=None,
                data=[],
                row_count=0,
                is_predefined=False,
                success=False,
                error="Unable to generate SQL",
                agent_used=used_agent,
                route_reason=decision.get("reason"),
            )

        cleaned_sql = sql_agent._clean_sql_string(sql_query) if hasattr(sql_agent, "_clean_sql_string") else sql_query
        if not sql_agent.validate_sql(cleaned_sql):
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
        
        # SQL Validator Agent: Validate and correct SQL before execution
        validator = SQLValidatorAgent(db=db)
        schema_info = sql_agent.get_schema_info() if hasattr(sql_agent, "get_schema_info") else None
        validation_result = validator.validate_and_correct(
            sql_query=cleaned_sql,
            original_question=request.question,
            schema_info=schema_info
        )
        
        # Store validator and schema_info for potential use in exception handler
        _validator = validator
        _schema_info = schema_info
        
        # Always use corrected SQL if available (even if validation says invalid - let execution try it)
        if validation_result.get("corrected_sql"):
            corrected_sql = validation_result["corrected_sql"]
            # Validate the corrected SQL is safe (no dangerous operations)
            if sql_agent.validate_sql(corrected_sql):
                cleaned_sql = corrected_sql
                used_agent = f"{used_agent}_validated"
                _logger.info(f"Using corrected SQL from validator: {used_agent}")
            else:
                # Corrected SQL has dangerous operations - reject it
                return ChatResponse(
                    answer=f"Error: Corrected SQL contains unsafe operations and was blocked.",
                    sql_query=cleaned_sql,
                    data=[],
                    row_count=0,
                    is_predefined=False,
                    success=False,
                    error="Unsafe SQL query detected in corrected SQL",
                    agent_used=used_agent,
                    route_reason=decision.get("reason"),
                )
        elif not validation_result["valid"]:
            # No corrected SQL available and validation failed
            error_msg = validation_result.get('error', 'Unknown error')
            # Check if error is related to missing columns/fields
            is_column_error = "Invalid column" in error_msg or "column" in error_msg.lower() or "42S22" in error_msg
            answer_text = f"Error: SQL query validation failed. {error_msg}"
            if is_column_error:
                answer_text += _get_biu_spoc_message()
            return ChatResponse(
                answer=answer_text,
                sql_query=cleaned_sql,
                data=[],
                row_count=0,
                is_predefined=False,
                success=False,
                error=error_msg,
                agent_used=used_agent,
                route_reason=decision.get("reason"),
            )

        # FollowUp Agent (before execution)
        if not request.skip_followups:
            followup_agent = _get_followup_agent()
            followup = followup_agent.analyze(db=db, question=request.question, sql_query=cleaned_sql)
            if followup.get("needs_followup"):
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

        try:
            from sqlalchemy import text
            db_result = db.execute(text(cleaned_sql))
            rows = db_result.fetchall()
            columns = db_result.keys()
            data = [dict(zip(columns, row)) for row in rows]
            row_count = len(data)

            # If query returns 0 rows and uses unnecessary joins, try simplified version
            if row_count == 0 and "JOIN" in cleaned_sql.upper() and "SUPER_LOAN_ACCOUNT_DIM" in cleaned_sql.upper():
                # Check if we can simplify by removing join with caselite_loan_applications
                cleaned_sql_upper = cleaned_sql.upper()
                if "CASELITE_LOAN_APPLICATIONS" in cleaned_sql_upper and re.search(r"(SLA|SUPER_LOAN_ACCOUNT_DIM)\.SCHEME", cleaned_sql_upper):
                    _logger.info("Query returned 0 rows with join, attempting simplified version...")
                    simplified_sql = _simplify_query_remove_unnecessary_join(cleaned_sql, request.question)
                    if simplified_sql and simplified_sql != cleaned_sql:
                        # Validate simplified SQL is safe
                        if sql_agent.validate_sql(simplified_sql):
                            try:
                                _logger.info(f"Trying simplified SQL: {simplified_sql}")
                                db_result = db.execute(text(simplified_sql))
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
                        # Fallback: Use validator to correct the SQL
                        _logger.info("Falling back to validator for SQL correction...")
                        correction_result = _validator.validate_and_correct(
                            sql_query=cleaned_sql,
                            original_question=request.question,
                            schema_info=_schema_info
                        )
                        if correction_result.get("corrected_sql") and correction_result["corrected_sql"] != cleaned_sql:
                            corrected_sql = correction_result["corrected_sql"]
                            if sql_agent.validate_sql(corrected_sql):
                                try:
                                    _logger.info(f"Trying validator-corrected SQL: {corrected_sql[:200]}...")
                                    db_result = db.execute(text(corrected_sql))
                                    rows = db_result.fetchall()
                                    columns = db_result.keys()
                                    data = [dict(zip(columns, row)) for row in rows]
                                    row_count = len(data)
                                    if row_count > 0:
                                        cleaned_sql = corrected_sql
                                        used_agent = f"{used_agent}_validator_corrected"
                                        _logger.info(f"✅ Validator-corrected query returned {row_count} rows")
                                except Exception as e:
                                    _logger.error(f"Validator-corrected query execution failed: {e}", exc_info=True)

            ql = request.question.lower()
            if row_count == 0:
                answer_text = "No records found matching your query."
            elif "how many" in ql or "count" in ql:
                answer_text = f"Found {row_count} record(s)."
            else:
                answer_text = f"Found {row_count} record(s)."

            return ChatResponse(
                answer=answer_text,
                sql_query=cleaned_sql,
                data=data,
                row_count=row_count,
                is_predefined=False,
                success=True,
                agent_used=used_agent,
                route_reason=decision.get("reason"),
            )
        except Exception as e:
            error_str = str(e)
            # Check if error is due to invalid column names
            if "Invalid column name" in error_str or "42S22" in error_str:
                # Try to correct using validator
                _logger.info(f"SQL execution failed with column error, attempting correction: {error_str}")
                correction_result = _validator.validate_and_correct(
                    sql_query=cleaned_sql,
                    original_question=request.question,
                    schema_info=_schema_info
                )
                
                if correction_result["valid"] and correction_result.get("corrected_sql"):
                    corrected_sql = correction_result["corrected_sql"]
                    # Validate corrected SQL is safe
                    if sql_agent.validate_sql(corrected_sql):
                        try:
                            # Retry with corrected SQL
                            db_result = db.execute(text(corrected_sql))
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
                            
                            return ChatResponse(
                                answer=answer_text,
                                sql_query=corrected_sql,
                                data=data,
                                row_count=row_count,
                                is_predefined=False,
                                success=True,
                                agent_used=f"{used_agent}_corrected",
                                route_reason=decision.get("reason"),
                            )
                        except Exception as retry_error:
                            _logger.error(f"Corrected SQL also failed: {retry_error}")
                            # If correction also fails, return error with SPOC info
                            answer_text = f"Error: Unable to execute the query. The requested column or field may not exist in the database schema.{_get_biu_spoc_message()}"
                            return ChatResponse(
                                answer=answer_text,
                                sql_query=corrected_sql,
                                data=[],
                                row_count=0,
                                is_predefined=False,
                                success=False,
                                error=str(retry_error),
                                agent_used=f"{used_agent}_correction_failed",
                                route_reason=decision.get("reason"),
                            )
                else:
                    # No correction available - return error with SPOC info
                    answer_text = f"Error: Unable to execute the query. The requested column or field may not exist in the database schema.{_get_biu_spoc_message()}"
                    return ChatResponse(
                        answer=answer_text,
                        sql_query=cleaned_sql,
                        data=[],
                        row_count=0,
                        is_predefined=False,
                        success=False,
                        error=error_str,
                        agent_used=f"{used_agent}_no_correction",
                        route_reason=decision.get("reason"),
                    )
            
            # If not a column error or correction failed, check if it's still column/field related
            is_column_error = "column" in error_str.lower() or "field" in error_str.lower() or "42S22" in error_str
            answer_text = f"Error executing SQL query: {error_str}"
            if is_column_error:
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
