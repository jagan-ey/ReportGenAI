"""
Intelligent Query Analyzer - Generates follow-up questions before executing queries
"""
from typing import Dict, List, Any, Optional
from app.core.config import settings
import json
import re
from datetime import datetime, timedelta

# Lazy import for LLM
_llm = None

def _get_llm():
    """Lazy initialization of Azure OpenAI LLM"""
    global _llm
    if _llm is None:
        try:
            from langchain_openai import AzureChatOpenAI
            _llm = AzureChatOpenAI(
                azure_endpoint=settings.AZURE_ENDPOINT,
                api_key=settings.OPENAI_API_KEY,
                api_version=settings.AZURE_API_VERSION,
                deployment_name=settings.AZURE_DEPLOYMENT_NAME,
                temperature=0.3  # Slightly higher for more natural questions
            )
        except Exception as e:
            print(f"Warning: Could not initialize LLM for query analysis: {e}")
            _llm = None
    return _llm


def analyze_query_for_followups(question: str, sql_query: Optional[str] = None, schema_info: Optional[str] = None) -> Dict[str, Any]:
    """
    Analyze a user query and generate intelligent follow-up questions
    
    Returns:
        {
            "needs_followup": bool,
            "followup_questions": List[Dict],
            "estimated_data_mb": Optional[float],
            "estimated_runtime_seconds": Optional[float],
            "analysis": str
        }
    """
    try:
        llm = _get_llm()
        if not llm:
            # Fallback: basic analysis without LLM
            return _basic_analysis(question, sql_query)
        
        # Build prompt for LLM to analyze query
        prompt = _build_analysis_prompt(question, sql_query, schema_info)
        
        # Get LLM response
        response = llm.invoke(prompt)
        analysis_text = response.content if hasattr(response, 'content') else str(response)
        
        # Parse LLM response
        return _parse_llm_analysis(analysis_text, question, sql_query)
        
    except Exception as e:
        print(f"Error in query analysis: {e}")
        # Fallback to basic analysis
        return _basic_analysis(question, sql_query)


def _build_analysis_prompt(question: str, sql_query: Optional[str], schema_info: Optional[str]) -> str:
    """Build prompt for LLM to analyze query and generate follow-ups"""
    
    prompt = f"""You are an intelligent query analyzer for a banking data platform. Analyze the following user question and determine if follow-up questions are needed before executing the query.

User Question: "{question}"
"""
    
    if sql_query:
        prompt += f"\nGenerated SQL Query:\n{sql_query}\n"
    
    if schema_info:
        prompt += f"\nDatabase Schema (relevant tables):\n{schema_info[:2000]}\n"  # Limit schema size
    
    prompt += """
Analyze this query and determine:
1. Does it need date/time clarification? (e.g., "as of today" vs "month end")
2. Does it need field mapping confirmation? (e.g., which field represents Re-KYC credit field)
3. Does it need date range confirmation? (e.g., specific date ranges for filters)
4. Does it need data volume/runtime estimation? (estimate based on table sizes and filters)

Generate follow-up questions in JSON format:
{
  "needs_followup": true/false,
  "followup_questions": [
    {
      "id": "date_clarification",
      "question": "Should the report be generated as of today or month end of November?",
      "type": "date_selection",
      "options": ["Today", "Month End (November)", "Custom Date"],
      "required": true
    },
    {
      "id": "field_mapping",
      "question": "X field will be used for identifying Re-KYC credit field, please confirm?",
      "type": "confirmation",
      "required": true
    },
    {
      "id": "date_range",
      "question": "Instances where Freeze code is 'RKYCF' and date is between 1st June to 30th Nov will be considered, please confirm?",
      "type": "confirmation",
      "required": true
    },
    {
      "id": "data_volume",
      "question": "This query will utilize approximately X MB of data to run, please confirm to proceed?",
      "type": "confirmation",
      "estimated_mb": 150.5,
      "estimated_seconds": 45,
      "required": true
    }
  ],
  "analysis": "Brief explanation of why these follow-ups are needed"
}

If no follow-ups are needed, return:
{
  "needs_followup": false,
  "followup_questions": [],
  "analysis": "Query is clear and can be executed directly"
}

Return ONLY valid JSON, no additional text.
"""
    
    return prompt


def _parse_llm_analysis(analysis_text: str, question: str, sql_query: Optional[str]) -> Dict[str, Any]:
    """Parse LLM response and extract follow-up questions"""
    try:
        # Try to extract JSON from response
        json_match = re.search(r'\{.*\}', analysis_text, re.DOTALL)
        if json_match:
            analysis_json = json.loads(json_match.group())
            
            # Estimate data volume and runtime if not provided
            if analysis_json.get("needs_followup", False):
                for q in analysis_json.get("followup_questions", []):
                    if q.get("id") == "data_volume" and not q.get("estimated_mb"):
                        # Estimate based on SQL query
                        estimates = _estimate_query_resources(sql_query)
                        q["estimated_mb"] = estimates.get("mb", 0)
                        q["estimated_seconds"] = estimates.get("seconds", 0)
                        if q.get("question"):
                            q["question"] = q["question"].replace("X MB", f"{estimates.get('mb', 0):.1f} MB")
                            q["question"] = q["question"].replace("X", f"{estimates.get('mb', 0):.1f}")
            
            return analysis_json
    except Exception as e:
        print(f"Error parsing LLM analysis: {e}")
    
    # Fallback to basic analysis
    return _basic_analysis(question, sql_query)


def _basic_analysis(question: str, sql_query: Optional[str]) -> Dict[str, Any]:
    """Basic analysis without LLM - uses pattern matching"""
    followups = []
    question_lower = question.lower()
    
    # Check for date ambiguity
    if any(word in question_lower for word in ["report", "generate", "show"]) and \
       not any(word in question_lower for word in ["today", "yesterday", "month", "date", "between"]):
        followups.append({
            "id": "date_clarification",
            "question": "Should the report be generated as of today or month end?",
            "type": "date_selection",
            "options": ["Today", "Month End", "Custom Date"],
            "required": True
        })
    
    # Check for field mapping needs (Re-KYC related)
    if "rekyc" in question_lower or "re-kyc" in question_lower:
        followups.append({
            "id": "field_mapping",
            "question": "RE_KYC_DUE_DATE field will be used for identifying Re-KYC credit field, please confirm?",
            "type": "confirmation",
            "required": True
        })
    
    # Check for freeze code queries
    if "freeze" in question_lower and "rkycf" in question_lower:
        followups.append({
            "id": "date_range",
            "question": "Instances where Freeze code is 'RKYCF' will be considered, please confirm?",
            "type": "confirmation",
            "required": True
        })
    
    # Estimate resources if SQL is available
    if sql_query:
        estimates = _estimate_query_resources(sql_query)
        if estimates.get("mb", 0) > 10:  # Only warn if > 10MB
            followups.append({
                "id": "data_volume",
                "question": f"This query will utilize approximately {estimates.get('mb', 0):.1f} MB of data and may take {estimates.get('seconds', 0)} seconds to run, please confirm to proceed?",
                "type": "confirmation",
                "estimated_mb": estimates.get("mb", 0),
                "estimated_seconds": estimates.get("seconds", 0),
                "required": True
            })
    
    return {
        "needs_followup": len(followups) > 0,
        "followup_questions": followups,
        "analysis": f"Generated {len(followups)} follow-up question(s) based on query analysis" if followups else "Query appears clear and can be executed directly"
    }


def _estimate_query_resources(sql_query: Optional[str]) -> Dict[str, float]:
    """Estimate data volume and runtime for a SQL query"""
    if not sql_query:
        return {"mb": 0, "seconds": 0}
    
    sql_upper = sql_query.upper()
    
    # Very basic estimation (can be improved with actual table statistics)
    estimated_mb = 0
    estimated_seconds = 0
    
    # Count table joins (more joins = more data)
    join_count = sql_upper.count("JOIN")
    
    # Check for aggregations (GROUP BY, COUNT, SUM)
    has_aggregation = any(keyword in sql_upper for keyword in ["GROUP BY", "COUNT", "SUM", "AVG", "MAX", "MIN"])
    
    # Check for WHERE clauses (filters reduce data)
    has_where = "WHERE" in sql_upper
    
    # Basic estimation logic
    base_mb = 5.0  # Base estimate
    estimated_mb = base_mb * (1 + join_count * 0.5)
    
    if has_aggregation:
        estimated_mb *= 1.5  # Aggregations process more data
    
    if has_where:
        estimated_mb *= 0.7  # Filters reduce data
    
    # Runtime estimation (rough: 1MB ≈ 0.3 seconds)
    estimated_seconds = estimated_mb * 0.3
    
    # Cap estimates
    estimated_mb = min(estimated_mb, 1000)  # Max 1GB
    estimated_seconds = min(estimated_seconds, 300)  # Max 5 minutes
    
    return {
        "mb": round(estimated_mb, 1),
        "seconds": round(estimated_seconds, 1)
    }


def generate_followup_questions(question: str, sql_query: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Generate follow-up questions for a query
    This is the main function to call
    """
    # Get schema info if available
    schema_info = None
    try:
        from app.services.sql_agent import get_sql_agent
        agent = get_sql_agent()
        schema_info = agent.get_schema_info()
    except:
        pass
    
    analysis = analyze_query_for_followups(question, sql_query, schema_info)
    return analysis.get("followup_questions", [])

