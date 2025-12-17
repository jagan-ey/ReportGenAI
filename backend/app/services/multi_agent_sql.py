"""
Multi-Agent SQL Generation System
Uses a primary agent for SQL generation and a fallback agent for refinement
"""
from typing import Optional, Dict, Any
from app.core.config import settings
from app.services.sql_agent import SQLAgentService
import logging

_logger = logging.getLogger(__name__)


class MultiAgentSQLService:
    """
    Multi-agent system for SQL generation:
    1. Primary Agent: Standard SQL agent with full toolkit
    2. Fallback Agent: Simplified agent for direct SQL generation when primary fails
    """
    
    def __init__(self, db_url: str):
        self.db_url = db_url
        self._primary_agent = None
        self._fallback_agent = None
        self._initialized = False
    
    def _ensure_initialized(self):
        """Lazy initialization of agents"""
        if self._initialized:
            return
        
        try:
            # Initialize primary agent (full-featured)
            self._primary_agent = SQLAgentService(self.db_url)
            _logger.info("✅ Primary SQL agent initialized")
            
            # Initialize fallback agent (simplified, direct SQL generation)
            self._fallback_agent = SQLAgentService(self.db_url)
            _logger.info("✅ Fallback SQL agent initialized")
            
            self._initialized = True
        except Exception as e:
            _logger.error(f"Failed to initialize multi-agent system: {str(e)}")
            raise
    
    def execute_query(self, question: str) -> Dict[str, Any]:
        """
        Execute query using multi-agent system:
        1. Try primary agent first
        2. If primary fails or gives up, use fallback agent with refined prompt
        """
        self._ensure_initialized()
        
        # Step 1: Try primary agent
        _logger.info(f"🔄 Primary agent attempting: {question[:100]}")
        primary_result = self._primary_agent.execute_query(question)
        
        if primary_result.get("success") and primary_result.get("sql_query"):
            _logger.info("✅ Primary agent succeeded")
            return primary_result
        
        # Step 2: Primary agent failed - try fallback with refined prompt
        _logger.warning(f"⚠️ Primary agent failed: {primary_result.get('error', 'Unknown error')}")
        _logger.info("🔄 Fallback agent attempting with refined prompt...")
        
        # Create a more direct prompt for the fallback agent
        refined_question = self._refine_question(question, primary_result.get("error", ""))
        fallback_result = self._fallback_agent.execute_query(refined_question)
        
        if fallback_result.get("success") and fallback_result.get("sql_query"):
            _logger.info("✅ Fallback agent succeeded")
            return fallback_result
        
        # Both agents failed
        _logger.error("❌ Both primary and fallback agents failed")
        return {
            "success": False,
            "error": (
                "Unable to generate SQL query. "
                "Primary agent error: " + (primary_result.get("error") or "Unknown") + ". "
                "Fallback agent error: " + (fallback_result.get("error") or "Unknown") + ". "
                "Please try rephrasing your question or use a predefined query."
            ),
            "answer": None,
            "sql_query": None
        }
    
    def _refine_question(self, original_question: str, error: str) -> str:
        """
        Refine the question with more context and instructions for the fallback agent
        """
        # Get schema info to help the agent
        try:
            schema_info = self._fallback_agent.get_schema_info()
            schema_preview = schema_info[:500] if schema_info else "Available tables in database"
        except:
            schema_preview = "Available tables in database"
        
        refined = f"""Generate a SQL SELECT query for the following question. 
You have access to the database schema. Focus on creating a valid SQL Server query.

Question: {original_question}

Previous attempt error: {error if error else "Primary agent could not generate SQL"}

Instructions:
1. Analyze the question carefully
2. Identify which tables and columns are needed
3. Write a valid SQL Server SELECT query
4. Use proper JOINs if multiple tables are needed
5. Use TOP instead of LIMIT for SQL Server
6. Return ONLY the SQL query, no explanations

Generate the SQL query now:"""
        
        return refined
    
    def validate_sql(self, sql: str) -> bool:
        """Validate SQL using primary agent's validation"""
        if self._primary_agent:
            return self._primary_agent.validate_sql(sql)
        return False
    
    def get_schema_info(self) -> str:
        """Get schema information"""
        self._ensure_initialized()
        return self._primary_agent.get_schema_info()
    
    def _clean_sql_string(self, sql: str) -> str:
        """Clean SQL string (delegate to primary agent)"""
        if self._primary_agent and hasattr(self._primary_agent, '_clean_sql_string'):
            return self._primary_agent._clean_sql_string(sql)
        # Fallback cleaning
        import re
        if not sql:
            return ""
        sql = re.sub(r'^```sql\s*', '', sql, flags=re.IGNORECASE | re.MULTILINE)
        sql = re.sub(r'^```\s*', '', sql, flags=re.IGNORECASE | re.MULTILINE)
        sql = re.sub(r'```\s*$', '', sql, flags=re.IGNORECASE | re.MULTILINE)
        sql = sql.strip().rstrip(';').strip()
        return sql

