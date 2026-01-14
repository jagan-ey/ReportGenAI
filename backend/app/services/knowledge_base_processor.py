"""
LLM-based Knowledge Base Processor

Intelligently processes database schema and sample data
to create a comprehensive knowledge base in the vector database.
"""

from typing import List, Dict, Optional, Any
import logging
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect, MetaData
from app.core.database import get_engine, get_db, get_kb_engine, get_kb_db
from app.core.config import settings
from app.services.vector_knowledge_base import get_vector_knowledge_base
from app.services.prompt_loader import get_prompt_loader
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

_logger = logging.getLogger(__name__)


class KnowledgeBaseProcessor:
    """
    Processes database schema, data, and documents to build knowledge base
    """
    
    def __init__(self):
        self.vector_kb = get_vector_knowledge_base()
        self._llm = None
        self._initialized = False
        self._prompt_loader = get_prompt_loader()
    
    def _ensure_initialized(self):
        """Lazy initialization of LLM"""
        if self._initialized:
            return
        
        try:
            self._llm = AzureChatOpenAI(
                azure_endpoint=settings.AZURE_ENDPOINT,
                api_key=settings.OPENAI_API_KEY,
                api_version=settings.AZURE_API_VERSION,
                deployment_name=settings.AZURE_DEPLOYMENT_NAME,
                temperature=0.0
            )
            self._initialized = True
            _logger.info("✅ Knowledge base processor LLM initialized")
        except Exception as e:
            _logger.error(f"Failed to initialize LLM: {e}")
            raise
    
    def process_database_schema(self, db: Session) -> int:
        """
        Process database schema to extract table and column information
        Uses the Knowledge Base database (regulatory data mart) connection
        
        Returns:
            Number of knowledge chunks created
        """
        self._ensure_initialized()
        chunks_created = 0
        
        try:
            # Use KB engine instead of main engine (regulatory data mart)
            engine = get_kb_engine()
            inspector = inspect(engine)
            tables = inspector.get_table_names(schema='dbo')
            
            _logger.info(f"Processing schema for {len(tables)} tables...")
            
            for table_name in tables:
                # Get columns
                columns = inspector.get_columns(table_name, schema='dbo')
                
                # Get primary keys
                pk_constraint = inspector.get_pk_constraint(table_name, schema='dbo')
                primary_keys = pk_constraint.get('constrained_columns', []) if pk_constraint else []
                
                # Get foreign keys
                foreign_keys = inspector.get_foreign_keys(table_name, schema='dbo')
                
                # Create table description using LLM
                table_info = self._create_table_description(
                    table_name=table_name,
                    columns=columns,
                    primary_keys=primary_keys,
                    foreign_keys=foreign_keys
                )
                
                # Add table-level knowledge with enriched business context
                synonyms_text = ""
                if table_info.get('business_synonyms'):
                    synonyms_text = f"\nBusiness Synonyms (alternative names users might use):\n" + "\n".join([f"  - {syn}" for syn in table_info.get('business_synonyms', [])])
                
                column_semantics_text = ""
                if table_info.get('column_semantics'):
                    column_semantics_text = "\nColumn Business Meanings:\n" + "\n".join([f"  - {col}: {meaning}" for col, meaning in table_info.get('column_semantics', {}).items()])
                
                example_queries_text = ""
                if table_info.get('example_queries'):
                    example_queries_text = "\nExample Natural Language Queries:\n" + "\n".join([f"  - {q}" for q in table_info.get('example_queries', [])])
                
                table_knowledge = f"""Table: {table_name}

Business Description: {table_info.get('description', 'N/A')}
{synonyms_text}

Columns:
{self._format_columns_for_kb(columns, primary_keys)}
{column_semantics_text}

Primary Keys: {', '.join(primary_keys) if primary_keys else 'None'}

Foreign Key Relationships:
{self._format_foreign_keys(foreign_keys)}

Business Use Cases:
{table_info.get('use_cases', 'N/A')}

Table Relationships:
{table_info.get('relationships', 'N/A')}
{example_queries_text}
"""
                
                self.vector_kb.add_knowledge(
                    content=table_knowledge,
                    metadata={
                        'type': 'table_schema',
                        'table': table_name,
                        'column_count': len(columns)
                    }
                )
                chunks_created += 1
                
                # Process each column individually
                for col in columns:
                    col_knowledge = self._create_column_knowledge(
                        table_name=table_name,
                        column=col,
                        is_primary_key=col['name'] in primary_keys
                    )
                    
                    if col_knowledge:
                        self.vector_kb.add_knowledge(
                            content=col_knowledge,
                            metadata={
                                'type': 'column_definition',
                                'table': table_name,
                                'column': col['name'],
                                'data_type': str(col.get('type', 'unknown'))
                            }
                        )
                        chunks_created += 1
            
            _logger.info(f"✅ Processed schema: {chunks_created} knowledge chunks created")
            return chunks_created
            
        except Exception as e:
            _logger.error(f"Error processing database schema: {e}", exc_info=True)
            return chunks_created
    
    def process_sample_data(self, db: Session, tables: Optional[List[str]] = None, sample_size: int = 20) -> int:
        """
        Process sample data from tables to extract patterns and valid values
        Uses the Knowledge Base database (regulatory data mart) connection
        
        Args:
            db: Database session (should be from KB database)
            tables: Optional list of table names. If None, processes all tables.
            sample_size: Number of sample rows to analyze per table (default: 20)
        
        Returns:
            Number of knowledge chunks created
        """
        self._ensure_initialized()
        chunks_created = 0
        
        try:
            # Use KB engine instead of main engine (regulatory data mart)
            engine = get_kb_engine()
            inspector = inspect(engine)
            table_list = tables or inspector.get_table_names(schema='dbo')
            
            _logger.info(f"Processing sample data from {len(table_list)} tables...")
            
            for table_name in table_list:
                try:
                    # Get sample data
                    query = text(f"SELECT TOP {sample_size} * FROM dbo.[{table_name}]")
                    result = db.execute(query)
                    rows = result.fetchall()
                    
                    if not rows:
                        continue
                    
                    # Get column names (result.keys() returns strings, not objects)
                    columns = list(result.keys())
                    
                    # Analyze data patterns using LLM
                    data_analysis = self._analyze_sample_data(
                        table_name=table_name,
                        columns=columns,
                        rows=rows[:min(20, len(rows))]  # Limit to 20 rows for LLM
                    )
                    
                    if data_analysis:
                        knowledge = f"""Table: {table_name} - Data Patterns and Valid Values

{data_analysis}
"""
                        self.vector_kb.add_knowledge(
                            content=knowledge,
                            metadata={
                                'type': 'data_patterns',
                                'table': table_name,
                                'sample_size': len(rows)
                            }
                        )
                        chunks_created += 1
                        
                except Exception as e:
                    _logger.warning(f"Error processing sample data for {table_name}: {e}")
                    continue
            
            _logger.info(f"✅ Processed sample data: {chunks_created} knowledge chunks created")
            return chunks_created
            
        except Exception as e:
            _logger.error(f"Error processing sample data: {e}", exc_info=True)
            return chunks_created
    
    def _create_table_description(
        self,
        table_name: str,
        columns: List[Dict],
        primary_keys: List[str],
        foreign_keys: List[Dict]
    ) -> Dict[str, str]:
        """Use LLM to create intelligent, enriched table description with business context"""
        try:
            columns_info = "\n".join([
                f"- {col['name']}: {col.get('type', 'unknown')}"
                for col in columns
            ])
            
            prompt = self._prompt_loader.get_prompt(
                "knowledge_base_processor",
                "table_description_template",
                table_name=table_name,
                columns_info=columns_info,
                primary_keys=', '.join(primary_keys) if primary_keys else 'None'
            )
            
            response = self._llm.invoke([HumanMessage(content=prompt)])
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Parse JSON response
            import json
            try:
                result = json.loads(content)
                # Ensure all fields exist
                return {
                    "description": result.get("description", ""),
                    "business_synonyms": result.get("business_synonyms", []),
                    "use_cases": result.get("use_cases", ""),
                    "column_semantics": result.get("column_semantics", {}),
                    "relationships": result.get("relationships", ""),
                    "example_queries": result.get("example_queries", [])
                }
            except Exception as e:
                _logger.warning(f"Could not parse JSON response: {e}. Using raw content.")
                return {
                    "description": content,
                    "business_synonyms": [],
                    "use_cases": "",
                    "column_semantics": {},
                    "relationships": "",
                    "example_queries": []
                }
                
        except Exception as e:
            _logger.warning(f"Error creating table description: {e}")
            return {
                "description": f"Table {table_name} with {len(columns)} columns",
                "business_synonyms": [],
                "use_cases": "",
                "column_semantics": {},
                "relationships": "",
                "example_queries": []
            }
    
    def _create_column_knowledge(
        self,
        table_name: str,
        column: Dict,
        is_primary_key: bool
    ) -> Optional[str]:
        """Use LLM to create intelligent, enriched column knowledge with business context"""
        try:
            prompt = self._prompt_loader.get_prompt(
                "knowledge_base_processor",
                "column_description_template",
                table_name=table_name,
                column_name=column['name'],
                data_type=column.get('type', 'unknown'),
                is_primary_key=str(is_primary_key)
            )
            
            response = self._llm.invoke([HumanMessage(content=prompt)])
            content = response.content if hasattr(response, 'content') else str(response)
            
            return f"""Column: {column['name']}
Table: {table_name}
Data Type: {column.get('type', 'unknown')}
Primary Key: {is_primary_key}

{content}
"""
            
        except Exception as e:
            _logger.warning(f"Error creating column knowledge: {e}")
            return None
    
    def _analyze_sample_data(
        self,
        table_name: str,
        columns: List[str],
        rows: List
    ) -> Optional[str]:
        """Use LLM to analyze sample data and extract patterns"""
        try:
            # Format sample data
            sample_data = []
            for row in rows[:10]:  # Limit to 10 rows for prompt
                row_dict = dict(zip(columns, row))
                sample_data.append(str(row_dict))
            
            prompt = self._prompt_loader.get_prompt(
                "knowledge_base_processor",
                "sample_data_analysis_template",
                table_name=table_name,
                columns=', '.join(columns),
                sample_data='\n'.join(sample_data)
            )
            
            response = self._llm.invoke([HumanMessage(content=prompt)])
            return response.content if hasattr(response, 'content') else str(response)
            
        except Exception as e:
            _logger.warning(f"Error analyzing sample data: {e}")
            return None
    
    def _format_columns_for_kb(self, columns: List[Dict], primary_keys: List[str]) -> str:
        """Format columns for knowledge base"""
        lines = []
        for col in columns:
            pk_marker = " (PRIMARY KEY)" if col['name'] in primary_keys else ""
            lines.append(f"  - {col['name']}: {col.get('type', 'unknown')}{pk_marker}")
        return "\n".join(lines)
    
    def _format_foreign_keys(self, foreign_keys: List[Dict]) -> str:
        """Format foreign keys for knowledge base"""
        if not foreign_keys:
            return "None"
        lines = []
        for fk in foreign_keys:
            lines.append(
                f"  - {', '.join(fk.get('constrained_columns', []))} -> "
                f"{fk.get('referred_table', 'unknown')}.{', '.join(fk.get('referred_columns', []))}"
            )
        return "\n".join(lines)
    
    def build_knowledge_base(
        self,
        db: Session,
        include_schema: bool = True,
        include_sample_data: bool = True
    ) -> Dict[str, int]:
        """
        Build complete knowledge base from all sources
        
        Returns:
            Dictionary with counts of chunks created by type
        """
        _logger.info("🚀 Starting knowledge base build...")
        
        stats = {
            'schema_chunks': 0,
            'data_chunks': 0
        }
        
        if include_schema:
            stats['schema_chunks'] = self.process_database_schema(db)
        
        if include_sample_data:
            stats['data_chunks'] = self.process_sample_data(db)
        
        total = sum(stats.values())
        _logger.info(f"✅ Knowledge base build complete! Total chunks: {total}")
        _logger.info(f"   - Schema: {stats['schema_chunks']}")
        _logger.info(f"   - Sample Data: {stats['data_chunks']}")
        
        return stats

