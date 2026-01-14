"""
Build Vector Knowledge Base

Script to initialize and build the vector knowledge base from:
1. Database schema
2. Sample data
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from app.core.database import get_db, get_engine, get_kb_db, get_kb_engine
from app.services.knowledge_base_processor import KnowledgeBaseProcessor
from app.services.vector_knowledge_base import get_vector_knowledge_base
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
_logger = logging.getLogger(__name__)


def main():
    """Main function to build knowledge base"""
    _logger.info("=" * 80)
    _logger.info("Building Vector Knowledge Base")
    _logger.info("=" * 80)
    
    # Initialize processor
    processor = KnowledgeBaseProcessor()
    vector_kb = get_vector_knowledge_base()
    
    # Get Knowledge Base database session (regulatory data mart)
    db_gen = get_kb_db()
    db = next(db_gen)
    
    try:
        # Ask user what to build
        print("\nWhat would you like to build?")
        print("1. Full knowledge base (schema + sample data)")
        print("2. Schema only")
        print("3. Schema + sample data")
        print("4. Clear existing knowledge base")
        print("5. Show statistics")
        
        choice = input("\nEnter choice (1-5): ").strip()
        
        if choice == "4":
            print("\nClear options:")
            print("1. Clear collection data only (keeps database files)")
            print("2. Clear collection data AND delete database files (complete cleanup)")
            clear_choice = input("Enter choice (1-2): ").strip()
            
            if clear_choice == "2":
                confirm = input("⚠️  WARNING: This will delete ALL database files. Are you sure? (yes/no): ").strip().lower()
                if confirm == "yes":
                    vector_kb.clear_all(delete_files=True)
                    _logger.info("✅ Knowledge base cleared and database files deleted")
                    _logger.info("ℹ️  Note: Some ChromaDB system tables may remain in chroma.sqlite3.")
                    _logger.info("   This is normal - they are empty system tables and will be recreated on next use.")
                else:
                    _logger.info("Cancelled")
            elif clear_choice == "1":
                confirm = input("Are you sure you want to clear all knowledge? (yes/no): ").strip().lower()
                if confirm == "yes":
                    vector_kb.clear_all(delete_files=False)
                    _logger.info("✅ Knowledge base cleared (database files kept)")
                else:
                    _logger.info("Cancelled")
            else:
                _logger.info("Invalid choice")
            return
        
        if choice == "5":
            stats = vector_kb.get_stats()
            _logger.info(f"\n📊 Knowledge Base Statistics:")
            _logger.info(f"   Total chunks: {stats['total_chunks']}")
            _logger.info(f"   Type distribution:")
            for kb_type, count in stats['type_distribution'].items():
                _logger.info(f"     - {kb_type}: {count}")
            return
        
        # Build knowledge base
        if choice == "1":
            stats = processor.build_knowledge_base(
                db=db,
                include_schema=True,
                include_sample_data=True
            )
        elif choice == "2":
            stats = processor.build_knowledge_base(
                db=db,
                include_schema=True,
                include_sample_data=False
            )
        elif choice == "3":
            stats = processor.build_knowledge_base(
                db=db,
                include_schema=True,
                include_sample_data=True
            )
        else:
            _logger.error("Invalid choice")
            return
        
        # Show final statistics
        try:
            final_stats = vector_kb.get_stats()
            if 'error' in final_stats:
                _logger.warning(f"⚠️  Could not retrieve stats: {final_stats.get('error', 'Unknown error')}")
                _logger.info(f"   Chunks created in this session: {sum(stats.values())}")
            else:
                _logger.info(f"\n📊 Final Knowledge Base Statistics:")
                _logger.info(f"   Total chunks: {final_stats['total_chunks']}")
                _logger.info(f"   Type distribution:")
                for kb_type, count in final_stats['type_distribution'].items():
                    _logger.info(f"     - {kb_type}: {count}")
        except Exception as e:
            _logger.warning(f"Could not get final stats: {e}")
            _logger.info(f"   Chunks created in this session: {sum(stats.values())}")
        
        _logger.info("\n✅ Knowledge base build complete!")
        
    except Exception as e:
        _logger.error(f"Error building knowledge base: {e}", exc_info=True)
    finally:
        db.close()


if __name__ == "__main__":
    main()

