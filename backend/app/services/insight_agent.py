"""
Insight Agent

Analyzes SQL query results and generates visualization recommendations and business insights.
Takes tabular data and produces chart configurations and natural language insights.
"""

from typing import Dict, Any, List, Optional
import logging
import json
import re

from app.core.config import settings
from app.services.prompt_loader import get_prompt_loader

_logger = logging.getLogger(__name__)


class InsightAgent:
    """
    Analyzes SQL results and generates visualization recommendations with business insights.
    """
    
    def __init__(self):
        self._llm = None
        self._initialized = False
        self._prompt_loader = get_prompt_loader()
    
    def _ensure_initialized(self):
        """Lazy initialization of LLM client"""
        if self._initialized:
            return
        
        try:
            from langchain_openai import AzureChatOpenAI
            
            self._llm = AzureChatOpenAI(
                azure_endpoint=settings.AZURE_ENDPOINT,
                api_key=settings.OPENAI_API_KEY,
                api_version=settings.AZURE_API_VERSION,
                deployment_name=settings.AZURE_DEPLOYMENT_NAME,
                temperature=0.3,  # Slightly higher for creative insights
            )
            self._initialized = True
            _logger.info("InsightAgent LLM initialized successfully")
        except Exception as e:
            _logger.error(f"Failed to initialize InsightAgent LLM: {e}")
            self._llm = None
            self._initialized = True
    
    def _detect_column_types(self, data: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        Detect column types (numeric, categorical, temporal) from sample data.
        
        Returns:
            Dict mapping column names to types: 'numeric', 'categorical', 'temporal', 'text'
        """
        if not data:
            return {}
        
        column_types = {}
        sample_row = data[0]
        
        for col_name, value in sample_row.items():
            if value is None:
                # Check other rows for non-null values
                for row in data[1:10]:  # Check up to 10 rows
                    if row.get(col_name) is not None:
                        value = row[col_name]
                        break
            
            if value is None:
                column_types[col_name] = 'unknown'
                continue
            
            # Check type
            if isinstance(value, (int, float)):
                column_types[col_name] = 'numeric'
            elif isinstance(value, str):
                # Check if it looks like a date
                if self._is_date_string(value):
                    column_types[col_name] = 'temporal'
                elif len(data) > 1 and len(set(row.get(col_name) for row in data[:min(20, len(data))])) < 10:
                    # If there are few unique values in sample, likely categorical
                    column_types[col_name] = 'categorical'
                else:
                    column_types[col_name] = 'text'
            else:
                # Date/datetime objects
                column_types[col_name] = 'temporal'
        
        return column_types
    
    def _is_date_string(self, value: str) -> bool:
        """Check if a string looks like a date"""
        if not isinstance(value, str):
            return False
        
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            r'\d{2}/\d{2}/\d{4}',  # MM/DD/YYYY
            r'\d{2}-\d{2}-\d{4}',  # DD-MM-YYYY
            r'\d{4}/\d{2}/\d{2}',  # YYYY/MM/DD
        ]
        
        for pattern in date_patterns:
            if re.match(pattern, value.strip()):
                return True
        return False
    
    def _create_data_summary(self, data: List[Dict[str, Any]], column_types: Dict[str, str]) -> str:
        """Create a concise summary of the data structure for LLM"""
        if not data:
            return "No data available"
        
        summary_parts = [
            f"Row count: {len(data)}",
            f"Columns: {len(data[0])}",
            "\nColumn details:"
        ]
        
        for col_name, col_type in column_types.items():
            # Get sample values
            sample_values = [row.get(col_name) for row in data[:5] if row.get(col_name) is not None]
            
            if col_type == 'numeric' and sample_values:
                values = [v for v in sample_values if isinstance(v, (int, float))]
                if values:
                    min_val = min(values)
                    max_val = max(values)
                    summary_parts.append(f"  - {col_name} ({col_type}): range {min_val} to {max_val}")
                else:
                    summary_parts.append(f"  - {col_name} ({col_type})")
            elif col_type == 'categorical' and sample_values:
                unique_vals = list(set([str(row.get(col_name)) for row in data[:20] if row.get(col_name) is not None]))[:5]
                summary_parts.append(f"  - {col_name} ({col_type}): values like {', '.join(unique_vals[:3])}")
            else:
                summary_parts.append(f"  - {col_name} ({col_type})")
        
        return "\n".join(summary_parts)
    
    def analyze(
        self,
        *,
        data: List[Dict[str, Any]],
        sql_query: str,
        question: str,
        schema_info: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze SQL results and generate visualization recommendations and insights.
        
        Args:
            data: List of dictionaries containing query results
            sql_query: The SQL query that was executed
            question: Original user question
            schema_info: Optional database schema information
        
        Returns:
            Dictionary with chart configuration and insights, or None if analysis fails
            {
                "chart_type": "bar" | "line" | "pie" | "scatter" | "table",
                "x_axis": str,
                "y_axis": List[str],
                "title": str,
                "grouping": Optional[str],
                "aggregation": Optional[str],
                "insights": List[str],
                "config": Dict  # Chart-specific configuration
            }
        """
        self._ensure_initialized()
        
        if not self._llm:
            _logger.warning("InsightAgent LLM not available, skipping insight generation")
            return None
        
        if not data:
            _logger.debug("No data to analyze for insights")
            return None
        
        try:
            # Detect column types
            column_types = self._detect_column_types(data)
            data_summary = self._create_data_summary(data, column_types)
            
            # Load prompt template
            system_prompt = self._prompt_loader.get_prompt("insight_agent", "system_prompt")
            user_prompt_template = self._prompt_loader.get_prompt("insight_agent", "user_prompt_template")
            
            # Format user prompt
            user_prompt = user_prompt_template.format(
                question=question,
                sql_query=sql_query,
                data_summary=data_summary,
                column_types=json.dumps(column_types, indent=2),
                sample_data=json.dumps(data[:3], indent=2, default=str)  # First 3 rows as sample
            )
            
            # Call LLM
            _logger.info(f"InsightAgent analyzing {len(data)} rows with {len(column_types)} columns")
            
            from langchain_core.messages import SystemMessage, HumanMessage
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = self._llm.invoke(messages)
            response_text = response.content.strip()
            
            # Parse JSON response
            insights = self._parse_insights_response(response_text)
            
            if insights:
                _logger.info(f"✅ InsightAgent generated {insights.get('chart_type', 'unknown')} chart recommendation")
                return insights
            else:
                _logger.warning("InsightAgent failed to parse LLM response")
                return None
                
        except Exception as e:
            _logger.error(f"InsightAgent analysis failed: {e}", exc_info=True)
            return None
    
    def _parse_insights_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Parse LLM response and extract insights JSON"""
        try:
            # Try to extract JSON from response
            # Handle markdown code blocks
            if "```json" in response_text:
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1)
            elif "```" in response_text:
                json_match = re.search(r'```\s*(\{.*?\})\s*```', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1)
            
            # Try to find JSON object
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(0)
            
            insights = json.loads(response_text)
            
            # Validate required fields
            if "chart_type" not in insights:
                _logger.warning("Missing chart_type in insights response")
                return None
            
            return insights
            
        except json.JSONDecodeError as e:
            _logger.error(f"Failed to parse insights JSON: {e}")
            _logger.debug(f"Response text: {response_text}")
            return None
    
    def should_generate_insights(self, row_count: int) -> bool:
        """
        Determine if insights should be generated based on row count threshold.
        
        Args:
            row_count: Number of rows in the result set
        
        Returns:
            True if insights should be generated, False otherwise
        """
        return row_count > settings.INSIGHT_MIN_ROWS
