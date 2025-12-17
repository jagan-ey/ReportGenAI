"""
Orchestrator Agent

Routes each user query to:
- predefined query execution (100% accuracy, direct SQLAlchemy execution)
- SQLMaker agent (LLM generates SQL for report/data queries)
- conversational agent (LLM answers non-data questions; no SQL)
"""

from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.services.predefined_queries_db import match_question_to_predefined
from app.services.conversational_agent import ConversationalAgent
from app.core.config import settings
import json


class OrchestratorAgent:
    def __init__(self, db_url: str):
        self.db_url = db_url
        self._conversational = ConversationalAgent(db_url)
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
        except Exception:
            self._llm = None
        self._initialized = True

    def _llm_route(self, question: str, previous_sql_query: Optional[str]) -> Dict[str, Any]:
        """
        LLM-based router to decide between:
          - conversational (explanations, schema questions, follow-ups about prior results)
          - report_sql (needs SQL to be generated and executed)
        Returns dict with {route, reason}
        """
        self._ensure_initialized()
        if not self._llm:
            # Safe fallback: use existing conversational keyword detector; otherwise treat as report/data.
            if self._conversational.is_conversational_query(question):
                return {"route": "conversational", "reason": "fallback_keyword"}
            return {"route": "report_sql", "reason": "fallback_default"}

        # Keep prompt simple but explicit; the LLM should infer meta follow-ups without a keyword list.
        sys_prompt = (
            "You are an orchestrator for a banking data assistant.\n"
            "Decide the correct route for the user's message.\n\n"
            "Routes:\n"
            "- conversational: user is chatting, asking for explanation, schema info, or asking follow-up/meta questions "
            "about the PREVIOUS result (e.g., asking where the data came from, what table was used, or what SQL ran).\n"
            "- report_sql: user is requesting a report/data retrieval that requires generating and executing SQL.\n\n"
            "Rules:\n"
            "- If the user asks about the previous result and previous_sql_query is provided, choose conversational.\n"
            "- Otherwise choose report_sql only when the user clearly asks to fetch/report data.\n"
            "- Return ONLY valid JSON with keys: route (conversational|report_sql), reason (short string).\n"
            "\n"
            "Examples:\n"
            "Input: {\"question\":\"List customers by state\",\"has_previous_sql_query\":false}\n"
            "Output: {\"route\":\"report_sql\",\"reason\":\"data_request\"}\n"
            "\n"
            "Input: {\"question\":\"hi, what can you do?\",\"has_previous_sql_query\":false}\n"
            "Output: {\"route\":\"conversational\",\"reason\":\"general_chat\"}\n"
            "\n"
            "Input: {\"question\":\"from which table we got this data?\",\"has_previous_sql_query\":true}\n"
            "Output: {\"route\":\"conversational\",\"reason\":\"followup_about_previous_result\"}\n"
            "\n"
            "Input: {\"question\":\"run the same report but for >3 months\",\"has_previous_sql_query\":true}\n"
            "Output: {\"route\":\"report_sql\",\"reason\":\"new_data_request\"}\n"
        )

        prev_sql = (previous_sql_query or "").strip()
        user_prompt = json.dumps(
            {
                "question": question,
                "has_previous_sql_query": bool(prev_sql),
                "previous_sql_query_preview": prev_sql[:500] if prev_sql else "",
            },
            ensure_ascii=False,
        )

        from langchain_core.messages import SystemMessage, HumanMessage
        resp = self._llm.invoke([SystemMessage(content=sys_prompt), HumanMessage(content=user_prompt)])
        txt = resp.content if hasattr(resp, "content") else str(resp)

        # Best-effort JSON parse
        try:
            parsed = json.loads(txt)
        except Exception:
            # Try to extract JSON object from text
            import re
            m = re.search(r"\{[\s\S]*\}", txt)
            if m:
                try:
                    parsed = json.loads(m.group(0))
                except Exception:
                    parsed = {}
            else:
                parsed = {}

        route = parsed.get("route")
        reason = parsed.get("reason", "llm_router")
        if route not in ("conversational", "report_sql"):
            # Conservative fallback
            route = "conversational" if prev_sql else "report_sql"
            reason = "llm_parse_fallback"
        return {"route": route, "reason": reason}

    def decide(
        self,
        *,
        db: Session,
        question: str,
        query_key: Optional[str] = None,
        use_predefined: bool = True,
        previous_sql_query: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Returns:
          { "route": "predefined", "predefined_key": str }
          { "route": "report_sql" }
          { "route": "conversational" }
        """

        if use_predefined:
            predefined_key = query_key or match_question_to_predefined(db, question)
            if predefined_key:
                return {"route": "predefined", "predefined_key": predefined_key}

        # Use LLM routing for everything that is not predefined.
        return self._llm_route(question, previous_sql_query)

    @property
    def conversational(self) -> ConversationalAgent:
        return self._conversational


