"""
Vector Database-based Knowledge Base Service

Uses ChromaDB to store and retrieve domain knowledge with semantic search.
Replaces the hardcoded knowledge_base.py with an intelligent, LLM-enhanced system.
"""

from typing import List, Dict, Optional, Any
import logging
import os

_logger = logging.getLogger(__name__)

# Lazy imports to avoid startup errors if dependencies aren't installed
_chromadb = None
_SentenceTransformer = None

def _import_chromadb():
    global _chromadb
    if _chromadb is None:
        try:
            import chromadb
            from chromadb.config import Settings
            _chromadb = {'chromadb': chromadb, 'Settings': Settings}
        except ImportError as e:
            _logger.warning(f"ChromaDB not available: {e}")
            _chromadb = False
    return _chromadb

def _import_sentence_transformers():
    global _SentenceTransformer
    if _SentenceTransformer is None:
        try:
            # Try to import with compatibility fix for huggingface_hub
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                from sentence_transformers import SentenceTransformer
                _SentenceTransformer = SentenceTransformer
        except ImportError as e:
            _logger.warning(f"SentenceTransformers not available: {e}")
            _logger.warning("Try: pip install --upgrade sentence-transformers huggingface-hub")
            _SentenceTransformer = False
        except Exception as e:
            _logger.warning(f"SentenceTransformers import error: {e}")
            _logger.warning("Try: pip install --upgrade sentence-transformers huggingface-hub")
            _SentenceTransformer = False
    return _SentenceTransformer


class VectorKnowledgeBase:
    """
    Vector database-based knowledge base using ChromaDB.
    Stores schema information, business rules, column definitions, and document knowledge.
    """
    
    def __init__(self, persist_directory: str = None):
        """
        Initialize vector knowledge base
        
        Args:
            persist_directory: Directory to persist ChromaDB data (defaults to settings.VECTOR_DB_PATH)
        """
        import os
        from app.core.config import settings
        
        # Resolve path to absolute path (relative to backend directory)
        base_path = persist_directory or settings.VECTOR_DB_PATH
        if not os.path.isabs(base_path):
            # Get backend directory (where this file is located: backend/app/services/)
            # Go up 3 levels: services -> app -> backend
            backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            # Remove 'backend/' prefix from base_path if it exists to avoid backend/backend
            # The config has "backend/data/vector_db", but we're already in backend directory
            if base_path.startswith('backend/'):
                base_path = base_path[8:]  # Remove 'backend/' prefix
            self.persist_directory = os.path.normpath(os.path.join(backend_dir, base_path))
            _logger.debug(f"Resolved vector DB path: {self.persist_directory}")
        else:
            self.persist_directory = os.path.normpath(base_path)
        
        # Ensure directory exists
        os.makedirs(self.persist_directory, exist_ok=True)
        self.client = None
        self.collection = None
        self.embedding_model = None
        self._initialized = False
        self._init_attempted = False  # Track if we've attempted initialization
        
    def _ensure_initialized(self):
        """Lazy initialization of ChromaDB and embedding model - non-blocking"""
        # If already successfully initialized, don't try again
        if self._initialized and self.collection is not None:
            return
        
        # If initialization failed before, don't retry (to avoid repeated errors)
        if hasattr(self, '_init_attempted') and self._init_attempted and not self._initialized:
            return
        
        self._init_attempted = True
        
        try:
            # Import dependencies
            chromadb_import = _import_chromadb()
            if chromadb_import is False:
                error_msg = "ChromaDB not available. Install with: pip install chromadb"
                _logger.error(error_msg)
                self._initialized = False
                return
            
            chromadb = chromadb_import['chromadb']
            Settings = chromadb_import['Settings']
            
            transformer_import = _import_sentence_transformers()
            if transformer_import is False:
                error_msg = "SentenceTransformers not available. Install with: pip install sentence-transformers"
                _logger.error(error_msg)
                self._initialized = False
                return
            
            SentenceTransformer = transformer_import
            
            # Initialize ChromaDB client
            self.client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Get or create collection (use collection name from settings)
            from app.core.config import settings
            collection_name = settings.KNOWLEDGE_BASE_COLLECTION
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"description": "CCM Platform Knowledge Base"}
            )
            
            # Initialize embedding model (this might take time - but only happens once)
            # Using a lightweight model for faster inference
            try:
                self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
                _logger.info(f"✅ Vector knowledge base initialized. Collection size: {self.collection.count()}")
                self._initialized = True
            except Exception as e:
                error_msg = f"Failed to load embedding model: {e}. Vector knowledge base disabled."
                _logger.error(error_msg)
                _logger.error("Try: pip install --upgrade sentence-transformers huggingface-hub")
                self._initialized = False
                self.collection = None
                self.client = None
            
        except Exception as e:
            error_msg = f"Failed to initialize vector knowledge base: {e}"
            _logger.error(error_msg)
            _logger.error("Please check that ChromaDB and SentenceTransformers are installed correctly.")
            self._initialized = False
            self.collection = None
            self.client = None
            self.embedding_model = None
    
    def add_knowledge(
        self,
        content: str,
        metadata: Dict[str, Any],
        knowledge_id: Optional[str] = None
    ) -> str:
        """
        Add knowledge chunk to vector database
        
        Args:
            content: The knowledge content (text)
            metadata: Metadata about the knowledge (table, column, type, etc.)
            knowledge_id: Optional unique ID. If not provided, generates one.
            
        Returns:
            The knowledge ID
        """
        self._ensure_initialized()
        
        # Check if actually initialized
        if not self._initialized or not self.collection or not self.embedding_model:
            _logger.debug("Vector knowledge base not available, skipping add_knowledge")
            return ""
        
        # Generate embedding
        embedding = self.embedding_model.encode(content).tolist()
        
        # Generate ID if not provided
        if not knowledge_id:
            import hashlib
            knowledge_id = hashlib.md5(
                f"{content}_{metadata.get('table', '')}_{metadata.get('type', '')}".encode()
            ).hexdigest()
        
        # Add to collection
        self.collection.add(
            ids=[knowledge_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[metadata]
        )
        
        _logger.debug(f"Added knowledge chunk: {knowledge_id}, type: {metadata.get('type', 'unknown')}")
        return knowledge_id
    
    def search(
        self,
        query: str,
        n_results: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search knowledge base using semantic similarity
        
        Args:
            query: Search query
            n_results: Number of results to return
            filter_metadata: Optional metadata filters (e.g., {"type": "column_definition"})
            
        Returns:
            List of knowledge chunks with scores
        """
        self._ensure_initialized()
        
        # Check if actually initialized
        if not self._initialized or not self.collection or not self.embedding_model:
            _logger.debug("Vector knowledge base not available, returning empty results")
            return []
        
        # Generate query embedding
        query_embedding = self.embedding_model.encode(query).tolist()
        
        # Build where clause for filtering (ChromaDB format)
        where = None
        if filter_metadata:
            # ChromaDB uses $in for list values
            where = {}
            for key, value in filter_metadata.items():
                if isinstance(value, list):
                    where[key] = {"$in": value}
                else:
                    where[key] = value
        
        # Search
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where
        )
        
        # Format results
        knowledge_chunks = []
        if results['ids'] and len(results['ids'][0]) > 0:
            for i in range(len(results['ids'][0])):
                knowledge_chunks.append({
                    'id': results['ids'][0][i],
                    'content': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'distance': results['distances'][0][i] if 'distances' in results else None
                })
        
        _logger.debug(f"Search query: '{query}' returned {len(knowledge_chunks)} results")
        return knowledge_chunks
    
    def get_relevant_knowledge(
        self,
        question: str,
        table_names: Optional[List[str]] = None,
        knowledge_types: Optional[List[str]] = None,
        max_results: int = 10,
        min_relevance_score: Optional[float] = None
    ) -> str:
        """
        Get relevant knowledge for a question, formatted for LLM context
        
        Args:
            question: User's question
            table_names: Optional list of table names to filter by
            knowledge_types: Optional list of knowledge types to filter by
                (e.g., ["column_definition", "business_rule", "example_query"])
            max_results: Maximum number of results to return (default: 10)
            min_relevance_score: Optional minimum relevance score (distance threshold)
                Lower distance = higher relevance. Typical threshold: 0.5-0.7
        
        Returns:
            Formatted knowledge context string
        """
        try:
            # Build metadata filter (ChromaDB format)
            filter_metadata = None
            if knowledge_types or table_names:
                filter_metadata = {}
                if knowledge_types:
                    filter_metadata['type'] = {"$in": knowledge_types}
                if table_names:
                    filter_metadata['table'] = {"$in": table_names}
            
            # Enhanced query: expand with synonyms and related terms
            expanded_query = self._expand_query(question)
            
            # Search for relevant knowledge with expanded query
            results = self.search(
                query=expanded_query,
                n_results=max_results * 2,  # Get more results, then filter by relevance
                filter_metadata=filter_metadata if filter_metadata else None
            )
            
            # Filter by relevance score if threshold provided
            if min_relevance_score is not None and results:
                filtered_results = []
                for result in results:
                    distance = result.get('distance', 1.0)
                    # ChromaDB uses cosine distance: 0 = identical, 1 = completely different
                    # Lower distance = higher relevance
                    if distance <= min_relevance_score:
                        filtered_results.append(result)
                results = filtered_results[:max_results]
            else:
                results = results[:max_results]
                
        except Exception as e:
            _logger.warning(f"Error retrieving knowledge from vector DB: {e}")
            return "No relevant knowledge available from knowledge base."
        
        if not results:
            return "No relevant knowledge found in knowledge base."
        
        # Format results for LLM context with better structure
        context_parts = ["=== RELEVANT KNOWLEDGE FROM KNOWLEDGE BASE ==="]
        
        # Group by type and table for better organization
        by_type_table = {}
        for result in results:
            kb_type = result['metadata'].get('type', 'unknown')
            table = result['metadata'].get('table', 'unknown')
            key = f"{kb_type}::{table}"
            if key not in by_type_table:
                by_type_table[key] = []
            by_type_table[key].append(result)
        
        # Sort by type priority (table_schema first, then column_definition, then data_patterns)
        type_priority = {
            'table_schema': 1,
            'column_definition': 2,
            'data_patterns': 3,
            'business_rule': 4
        }
        
        sorted_keys = sorted(
            by_type_table.keys(),
            key=lambda k: (type_priority.get(k.split('::')[0], 99), k)
        )
        
        # Format each type/table combination
        for key in sorted_keys:
            kb_type, table = key.split('::')
            chunks = by_type_table[key]
            
            # Limit chunks per type/table combination
            chunks = chunks[:3]
            
            context_parts.append(f"\n--- {kb_type.upper().replace('_', ' ')}: {table} ---")
            for chunk in chunks:
                column = chunk['metadata'].get('column', '')
                if column:
                    context_parts.append(f"\n[Column: {column}]")
                
                # Add relevance indicator if available
                distance = chunk.get('distance')
                if distance is not None:
                    relevance = "High" if distance < 0.3 else "Medium" if distance < 0.6 else "Low"
                    context_parts.append(f"[Relevance: {relevance}]")
                
                context_parts.append(chunk['content'])
                context_parts.append("")  # Blank line between chunks
        
        return "\n".join(context_parts)
    
    def _expand_query(self, query: str) -> str:
        """
        Expand search query with synonyms and related terms to improve retrieval
        
        Args:
            query: Original search query
        
        Returns:
            Expanded query string
        """
        # Simple expansion: add common synonyms and variations
        # This helps with semantic search when exact terms don't match
        
        # Common banking/financial term expansions
        expansions = {
            'loan': ['loan', 'lending', 'credit', 'advance'],
            'customer': ['customer', 'client', 'account holder', 'borrower'],
            'account': ['account', 'acct', 'acc'],
            'active': ['active', 'current', 'open', 'live'],
            'closed': ['closed', 'inactive', 'terminated', 'settled'],
            'balance': ['balance', 'amount', 'outstanding'],
            'date': ['date', 'time', 'timestamp', 'when'],
            'status': ['status', 'state', 'condition', 'flag']
        }
        
        query_lower = query.lower()
        expanded_terms = [query]  # Always include original
        
        # Add expansions for terms found in query
        for term, synonyms in expansions.items():
            if term in query_lower:
                expanded_terms.extend(synonyms)
        
        # Combine into expanded query (use original + key synonyms)
        # Limit to avoid diluting the query too much
        if len(expanded_terms) > 1:
            # Use original query as primary, add 2-3 most relevant synonyms
            expanded = f"{query} {' '.join(expanded_terms[1:4])}"
            return expanded
        
        return query
    
    def clear_all(self, delete_files: bool = False):
        """
        Clear all knowledge from the database
        
        Args:
            delete_files: If True, deletes the entire ChromaDB database directory. 
                         If False (default), only clears the collection data.
        
        Note:
            After deletion, some ChromaDB system tables may remain in chroma.sqlite3
            (e.g., embeddings_queue, embeddings_fts, documents_fts). This is normal
            ChromaDB behavior - these are empty system tables used for internal
            operations. They will be recreated on next initialization and don't
            contain any user data.
        """
        self._ensure_initialized()
        
        # Check if collection is available
        if not self.collection:
            _logger.error("Cannot clear knowledge base: ChromaDB collection not initialized. Check if ChromaDB and SentenceTransformers are installed.")
            raise RuntimeError(
                "Vector knowledge base not initialized. "
                "Please ensure ChromaDB and SentenceTransformers are installed: "
                "pip install chromadb sentence-transformers"
            )
        
        # Delete all documents from the collection
        try:
            # Get all IDs first
            all_data = self.collection.get()
            if all_data['ids'] and len(all_data['ids']) > 0:
                self.collection.delete(ids=all_data['ids'])
                _logger.info(f"✅ Cleared {len(all_data['ids'])} knowledge chunks from vector database")
            else:
                _logger.info("ℹ️  Knowledge base is already empty")
            
            # Optionally delete the entire database directory
            if delete_files:
                import shutil
                import time
                import gc
                
                # Properly close client and collection first to release file locks
                # Order matters: close collection first, then client
                collection_path = None
                if self.collection:
                    collection_path = self.persist_directory
                    self.collection = None
                
                if self.client:
                    try:
                        # Try to reset the client to release all connections
                        # ChromaDB PersistentClient doesn't have explicit close method
                        # Setting to None and forcing garbage collection helps release file handles
                        self.client = None
                    except:
                        pass
                
                # Reset initialization state BEFORE deleting files
                self._initialized = False
                self._init_attempted = False
                self.embedding_model = None
                
                # Force garbage collection to release file handles (Windows needs this)
                gc.collect()
                time.sleep(1.5)  # Give Windows more time to release file locks
                
                # Delete the entire directory
                if os.path.exists(self.persist_directory):
                    try:
                        # Try to delete files individually first (more reliable on Windows)
                        for root, dirs, files in os.walk(self.persist_directory, topdown=False):
                            for name in files:
                                file_path = os.path.join(root, name)
                                try:
                                    os.chmod(file_path, 0o777)  # Make writable
                                    os.remove(file_path)
                                except PermissionError:
                                    _logger.warning(f"Could not delete {file_path}, will retry with rmtree")
                            for name in dirs:
                                try:
                                    os.rmdir(os.path.join(root, name))
                                except:
                                    pass
                        
                        # Final cleanup with rmtree
                        if os.path.exists(self.persist_directory):
                            shutil.rmtree(self.persist_directory, ignore_errors=True)
                        
                        _logger.info(f"✅ Deleted ChromaDB database directory: {self.persist_directory}")
                    except (PermissionError, OSError) as e:
                        _logger.error(f"❌ Cannot delete database files - they may be locked by another process.")
                        _logger.error(f"   Directory: {self.persist_directory}")
                        _logger.error(f"   Error: {e}")
                        _logger.error(f"   Please:")
                        _logger.error(f"   1. Close any running FastAPI/uvicorn servers")
                        _logger.error(f"   2. Close any Python processes using the knowledge base")
                        _logger.error(f"   3. Manually delete the directory if needed: {self.persist_directory}")
                        raise RuntimeError(
                            f"Cannot delete database files - they are locked. "
                            f"Please close any other processes (FastAPI server, Python scripts) and try again. "
                            f"Directory: {self.persist_directory}"
                        ) from e
                    
                    # Reset initialization state so it can be recreated
                    self._initialized = False
                    self._init_attempted = False
                    self.embedding_model = None
                else:
                    _logger.warning(f"Database directory does not exist: {self.persist_directory}")
        except Exception as e:
            _logger.error(f"Error clearing knowledge base: {e}")
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the knowledge base"""
        try:
            self._ensure_initialized()
            count = self.collection.count()
            
            # Get type distribution
            all_data = self.collection.get()
            type_dist = {}
            if all_data['metadatas']:
                for metadata in all_data['metadatas']:
                    kb_type = metadata.get('type', 'unknown')
                    type_dist[kb_type] = type_dist.get(kb_type, 0) + 1
            
            return {
                'total_chunks': count,
                'type_distribution': type_dist
            }
        except Exception as e:
            _logger.warning(f"Could not get stats (vector KB not initialized): {e}")
            return {
                'total_chunks': 0,
                'type_distribution': {},
                'error': str(e)
            }


# Singleton instance
_vector_kb = None

def get_vector_knowledge_base() -> VectorKnowledgeBase:
    """Get singleton vector knowledge base instance"""
    global _vector_kb
    if _vector_kb is None:
        _vector_kb = VectorKnowledgeBase()
    return _vector_kb

