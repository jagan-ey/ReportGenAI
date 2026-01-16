#!/bin/bash
set -e

echo "🚀 Starting GenAI CCM Platform Backend..."

# Flag file to track if initialization has been done
INIT_FLAG="/app/data/.initialized"

# Check if this is the first run
if [ ! -f "$INIT_FLAG" ]; then
    echo "📦 First run detected - running initialization scripts..."
    
    # Wait a bit for database to be ready
    echo "⏳ Waiting for database connection..."
    sleep 5
    
    # Run seed_users.py
    echo "🌱 Seeding initial users..."
    if python scripts/seed_users.py; then
        echo "✅ Users seeded successfully"
    else
        echo "⚠️  Warning: User seeding failed, but continuing..."
    fi
    
    # Run build_knowledge_base.py (non-interactive mode)
    echo "🧠 Building knowledge base..."
    if [ "${SKIP_KB_BUILD}" != "true" ]; then
        # Use environment variable to control KB build
        # Default: build full knowledge base (schema + sample data)
        export KB_BUILD_MODE=${KB_BUILD_MODE:-full}
        
        if [ "$KB_BUILD_MODE" = "full" ]; then
            echo "Building full knowledge base (schema + sample data)..."
            python -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path('.')))
from app.services.knowledge_base_processor import KnowledgeBaseProcessor
from app.services.vector_knowledge_base import get_vector_knowledge_base
from app.core.database import get_kb_db
import logging
logging.basicConfig(level=logging.INFO)
_logger = logging.getLogger(__name__)
processor = KnowledgeBaseProcessor()
db_gen = get_kb_db()
db = next(db_gen)
try:
    _logger.info('Building full knowledge base...')
    stats = processor.build_knowledge_base(db=db, include_schema=True, include_sample_data=True)
    _logger.info(f'Knowledge base built: {stats}')
    _logger.info('✅ Knowledge base initialization complete!')
except Exception as e:
    _logger.error(f'Error building knowledge base: {e}')
finally:
    db.close()
" 2>&1 | tee /app/logs/kb_build.log || echo "⚠️  Warning: Knowledge base build failed, but continuing..."
        elif [ "$KB_BUILD_MODE" = "schema" ]; then
            echo "Building knowledge base (schema only)..."
            python -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path('.')))
from app.services.knowledge_base_processor import KnowledgeBaseProcessor
from app.core.database import get_kb_db
import logging
logging.basicConfig(level=logging.INFO)
_logger = logging.getLogger(__name__)
processor = KnowledgeBaseProcessor()
db_gen = get_kb_db()
db = next(db_gen)
try:
    stats = processor.build_knowledge_base(db=db, include_schema=True, include_sample_data=False)
    _logger.info(f'Schema knowledge base built: {stats}')
finally:
    db.close()
" || echo "⚠️  Warning: Schema build failed, but continuing..."
        else
            echo "ℹ️  Skipping knowledge base build (KB_BUILD_MODE=$KB_BUILD_MODE)"
        fi
    else
        echo "ℹ️  Skipping knowledge base build (SKIP_KB_BUILD=true)"
    fi
    
    # Create the flag file to indicate initialization is complete
    touch "$INIT_FLAG"
    echo "✅ Initialization complete! Flag created at $INIT_FLAG"
else
    echo "ℹ️  Not first run - skipping initialization scripts"
fi

# Start the main application
echo "🚀 Starting FastAPI application..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
