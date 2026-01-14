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
from app.services.prompt_loader import get_prompt_loader
from app.core.config import settings
import json


class OrchestratorAgent:
    def __init__(self, db_url: str):
        self.db_url = db_url
        self._conversational = ConversationalAgent(db_url)
        self._llm = None
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

        # Load prompt from external file
        sys_prompt = self._prompt_loader.get_prompt("orchestrator", "system_prompt")

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


