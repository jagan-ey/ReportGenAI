"""
LLM-based Knowledge Base Processor

Intelligently processes database schema, sample data, and business documents
to create a comprehensive knowledge base in the vector database.
"""

from typing import List, Dict, Optional, Any
import logging
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect, MetaData
from app.core.database import get_engine, get_db, get_kb_engine, get_kb_db
from app.core.config import settings
from app.services.vector_knowledge_base import get_vector_knowledge_base
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
import os
from pathlib import Path

_logger = logging.getLogger(__name__)


class KnowledgeBaseProcessor:
    """
    Processes database schema, data, and documents to build knowledge base
    """
    
    def __init__(self):
        self.vector_kb = get_vector_knowledge_base()
        self._llm = None
        self._initialized = False
    
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
    
    def process_sample_data(self, db: Session, tables: Optional[List[str]] = None, sample_size: int = 100) -> int:
        """
        Process sample data from tables to extract patterns and valid values
        Uses the Knowledge Base database (regulatory data mart) connection
        
        Args:
            db: Database session (should be from KB database)
            tables: Optional list of table names. If None, processes all tables.
            sample_size: Number of sample rows to analyze per table
        
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
                        rows=rows[:min(50, len(rows))]  # Limit to 50 rows for LLM
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
    
    def process_business_documents(self, documents_dir: str = "./business_documents") -> int:
        """
        Process business documents (PDF, DOCX, TXT) to extract domain knowledge
        
        Args:
            documents_dir: Directory containing business documents
            
        Returns:
            Number of knowledge chunks created
        """
        self._ensure_initialized()
        chunks_created = 0
        
        try:
            doc_path = Path(documents_dir)
            if not doc_path.exists():
                _logger.warning(f"Documents directory not found: {documents_dir}")
                return 0
            
            _logger.info(f"Processing business documents from {documents_dir}...")
            
            # Process PDF files
            for pdf_file in doc_path.glob("*.pdf"):
                try:
                    content = self._extract_pdf_content(str(pdf_file))
                    if content:
                        chunks = self._chunk_document(content, pdf_file.name)
                        for chunk in chunks:
                            self.vector_kb.add_knowledge(
                                content=chunk,
                                metadata={
                                    'type': 'business_document',
                                    'source': pdf_file.name,
                                    'format': 'pdf'
                                }
                            )
                            chunks_created += 1
                except Exception as e:
                    _logger.warning(f"Error processing PDF {pdf_file.name}: {e}")
            
            # Process DOCX files
            for docx_file in doc_path.glob("*.docx"):
                try:
                    content = self._extract_docx_content(str(docx_file))
                    if content:
                        chunks = self._chunk_document(content, docx_file.name)
                        for chunk in chunks:
                            self.vector_kb.add_knowledge(
                                content=chunk,
                                metadata={
                                    'type': 'business_document',
                                    'source': docx_file.name,
                                    'format': 'docx'
                                }
                            )
                            chunks_created += 1
                except Exception as e:
                    _logger.warning(f"Error processing DOCX {docx_file.name}: {e}")
            
            # Process TXT files
            for txt_file in doc_path.glob("*.txt"):
                try:
                    with open(txt_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    if content:
                        chunks = self._chunk_document(content, txt_file.name)
                        for chunk in chunks:
                            self.vector_kb.add_knowledge(
                                content=chunk,
                                metadata={
                                    'type': 'business_document',
                                    'source': txt_file.name,
                                    'format': 'txt'
                                }
                            )
                            chunks_created += 1
                except Exception as e:
                    _logger.warning(f"Error processing TXT {txt_file.name}: {e}")
            
            _logger.info(f"✅ Processed business documents: {chunks_created} knowledge chunks created")
            return chunks_created
            
        except Exception as e:
            _logger.error(f"Error processing business documents: {e}", exc_info=True)
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
            
            prompt = f"""You are a database analyst creating enriched documentation for a banking/financial services database table.

Table Name: {table_name}
Columns:
{columns_info}

Primary Keys: {', '.join(primary_keys) if primary_keys else 'None'}

Analyze this table and provide RICH, BUSINESS-CONTEXTUAL information:

1. **Business Description**: What does this table represent in banking/financial terms? (e.g., "Customer master data", "Loan account details", "Gold collateral information")

2. **Business Synonyms & Alternative Names**: What are common business terms or alternative names users might use to refer to this table? 
   - For example, if table is "super_loan_account_dim", synonyms might be: "Loans", "Loan Accounts", "Loan Details", "Active Loans"
   - List 5-10 common synonyms that users might use in natural language queries

3. **Key Business Use Cases**: What types of queries or reports would use this table?
   - Example: "Finding all active loan accounts", "Checking loan tenure", "Viewing loan account balances"

4. **Column Semantics**: For key columns, what do they represent in business terms?
   - Map technical column names to business concepts (e.g., "ACCNO" = "Loan Account Number", "TENURE" = "Loan Tenure in Months")

5. **Relationships**: How does this table relate to other tables? What joins are commonly used?

6. **Example Natural Language Queries**: Provide 3-5 example questions users might ask that would query this table
   - Example: "Show me all loans", "Find loan accounts with tenure > 12 months", "List active loan accounts"

Return JSON format:
{{
    "description": "Clear business description",
    "business_synonyms": ["synonym1", "synonym2", ...],
    "use_cases": "Detailed use cases",
    "column_semantics": {{"COLUMN_NAME": "business meaning", ...}},
    "relationships": "Table relationships",
    "example_queries": ["query1", "query2", ...]
}}
"""
            
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
            prompt = f"""You are a database analyst creating enriched documentation for a banking/financial services database column.

Table: {table_name}
Column: {column['name']}
Data Type: {column.get('type', 'unknown')}
Primary Key: {is_primary_key}

Provide RICH, BUSINESS-CONTEXTUAL information:

1. **Business Meaning**: What does this column represent in banking/financial terms?
   - Be specific: "Loan Account Number" not just "Account Number"
   - Include context: "Loan tenure in months" not just "Tenure"

2. **Business Synonyms**: What are alternative names or terms users might use to refer to this column?
   - For example, "ACCNO" might be referred to as "Account Number", "Loan Account Number", "Account ID"
   - List 3-5 common synonyms

3. **Valid Values & Patterns**: What are common valid values, formats, or patterns?
   - For codes: List common code values and their meanings
   - For dates: Explain date format and business meaning
   - For amounts: Explain currency and precision

4. **Business Rules**: What business rules or constraints apply?
   - Example: "Must be unique", "Cannot be null for active accounts", "Must be >= 0"

5. **Usage in Queries**: How is this column typically used in SQL queries?
   - Example: "Used in WHERE clauses to filter by account", "Used in SELECT to display loan details"

6. **Semantic Mapping**: Map this technical column name to business concepts
   - Example: "ACCNO" maps to business concepts: "Loan Account", "Account Number", "Loan ID"

Return a clear, structured description suitable for SQL query generation.
"""
            
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
            
            prompt = f"""Analyze this sample data from database table and extract:
1. Valid values and patterns for each column
2. Business rules or constraints evident from the data
3. Common value combinations
4. Data quality observations

Table: {table_name}
Columns: {', '.join(columns)}

Sample Data:
{chr(10).join(sample_data)}

Provide a clear analysis suitable for SQL query generation.
"""
            
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
    
    def _extract_pdf_content(self, pdf_path: str) -> Optional[str]:
        """Extract text content from PDF"""
        try:
            from pypdf import PdfReader
            reader = PdfReader(pdf_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text.strip()
        except Exception as e:
            _logger.warning(f"Error extracting PDF content: {e}")
            return None
    
    def _extract_docx_content(self, docx_path: str) -> Optional[str]:
        """Extract text content from DOCX"""
        try:
            from docx import Document
            doc = Document(docx_path)
            text = "\n".join([para.text for para in doc.paragraphs])
            return text.strip()
        except Exception as e:
            _logger.warning(f"Error extracting DOCX content: {e}")
            return None
    
    def _chunk_document(self, content: str, source: str, chunk_size: int = 1000) -> List[str]:
        """Split document into chunks for vector storage"""
        # Simple chunking by character count
        chunks = []
        words = content.split()
        current_chunk = []
        current_size = 0
        
        for word in words:
            word_size = len(word) + 1  # +1 for space
            if current_size + word_size > chunk_size and current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = [word]
                current_size = word_size
            else:
                current_chunk.append(word)
                current_size += word_size
        
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        
        return chunks
    
    def build_knowledge_base(
        self,
        db: Session,
        include_schema: bool = True,
        include_sample_data: bool = True,
        include_documents: bool = True,
        documents_dir: str = "./business_documents"
    ) -> Dict[str, int]:
        """
        Build complete knowledge base from all sources
        
        Returns:
            Dictionary with counts of chunks created by type
        """
        _logger.info("🚀 Starting knowledge base build...")
        
        stats = {
            'schema_chunks': 0,
            'data_chunks': 0,
            'document_chunks': 0
        }
        
        if include_schema:
            stats['schema_chunks'] = self.process_database_schema(db)
        
        if include_sample_data:
            stats['data_chunks'] = self.process_sample_data(db)
        
        if include_documents:
            stats['document_chunks'] = self.process_business_documents(documents_dir)
        
        total = sum(stats.values())
        _logger.info(f"✅ Knowledge base build complete! Total chunks: {total}")
        _logger.info(f"   - Schema: {stats['schema_chunks']}")
        _logger.info(f"   - Sample Data: {stats['data_chunks']}")
        _logger.info(f"   - Documents: {stats['document_chunks']}")
        
        return stats

