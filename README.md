# GenAI Continuous Controls Monitoring (CCM) Platform

GenAI chat + SQL for banking controls monitoring. Multi-agent LLMs, vector knowledge base (RAG), and strict DB separation.

## What it does
- Natural language to SQL with Azure OpenAI (GPT-4o).
- Conversation mode (no SQL) vs Report mode (SQL generation + execution).
- Multi-agent routing: Orchestrator, SQLMaker, SQL Validator (fallback), FollowUp, Conversational.
- Vector knowledge base (ChromaDB) enriched with schema, sample data, and business docs.
- Saved queries with guaranteed accuracy.

## Databases
- **Application DB (`ccm_genai`)**: users, predefined_queries, approval_requests, scheduled_reports.
- **Knowledge Base DB (`axis_reg_mart`)**: regulatory/star-schema tables (e.g., SUPER_CUSTOMER_DIM, SUPER_LOAN_ACCOUNT_DIM, GOLD_COLLATERAL_DIM, etc.). Used for SQL generation/execution and KB builds.

## Architecture (high level)
- React frontend chat with mode toggle (Conversation/Report), follow-ups, agent badges.
- FastAPI backend orchestrating agents and SQL execution.
- ChromaDB vector store for schema/business knowledge.
- Two SQL Server DBs: app DB (`ccm_genai`) and KB/data mart (`axis_reg_mart`).

## Quick start (backend)
```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac
pip install -r requirements.txt

# configure .env (copy env.example)
# - Azure OpenAI: AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_CHAT_DEPLOYMENT, AZURE_OPENAI_API_VERSION
# - App DB: DB_SERVER, DB_NAME=ccm_genai, DB_USERNAME, DB_PASSWORD
# - KB DB:  KB_DB_SERVER, KB_DB_NAME=axis_reg_mart, KB_DB_USERNAME, KB_DB_PASSWORD

python scripts/init_db.py             # create app tables
python scripts/build_knowledge_base.py # build vector KB (choose schema/sample/doc options)
uvicorn app.main:app --reload
```

## Quick start (frontend)
```bash
cd frontend
npm install
npm run dev
```

## Using the chat
- Conversation mode: answers via conversational agent (no SQL, no DB execution).
- Report mode: routes to SQLMaker (uses KB schema from `axis_reg_mart`); executes SQL on KB DB; FollowUp may ask clarifications; Validator fixes failed SQL.
- If report mode can’t form SQL, user is asked to switch to Conversation mode.
- Saved queries run directly from `predefined_queries` (still executed on KB DB).

## Knowledge base (RAG)
- Built from the KB DB (`axis_reg_mart`) plus optional business docs.
- `scripts/build_knowledge_base.py` options:
  1) Full (schema + sample data + docs)
  2) Schema only
  3) Schema + sample data
  4) Clear (data only or delete files)
  5) Show stats
- `knowledge_base_processor.py`:
  - Introspects KB DB tables/columns/PKs/FKs.
  - LLM-enriches with business descriptions, synonyms, column semantics, relationships, and example NL queries.
  - Optionally samples data for value patterns; ingests PDF/DOCX/TXT business docs.
  - Stores chunks in ChromaDB via `vector_knowledge_base.py`.

## Key agents
- Orchestrator: decides predefined vs report SQL vs conversational.
- SQLMaker: SQL generation with schema from KB and RAG context.
- SQL Validator: fallback correction when SQL fails.
- FollowUp: asks clarifications (date/freshness/filters/joins/etc.) before execution.
- Conversational: platform/schema Q&A; used when mode=conversation or router deems non-SQL.

## Safety & validation
- SELECT-only, dangerous keyword blocking, schema validation.
- Separate connections for app DB vs KB DB; SQL execution happens on KB DB.
- Semantic mismatch check to avoid wrong-column substitutions.

## Maintenance tips
- After schema changes in `axis_reg_mart`, rebuild the KB (`build_knowledge_base.py`).
- Ensure KB DB has the needed tables (e.g., loan tables) or SQLMaker will map to nearest table.
- Clear/clean vector DB via the build script option 4 (handles Windows locks).

## Environment variables (essentials)
```env
# Azure OpenAI
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=...
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2025-01-01-preview

# App DB
DB_SERVER=...
DB_NAME=ccm_genai
DB_USERNAME=...
DB_PASSWORD=...

# Knowledge Base DB
KB_DB_SERVER=...        # optional; defaults to DB_SERVER
KB_DB_NAME=axis_reg_mart
KB_DB_USERNAME=...      # optional; defaults to DB_USERNAME
KB_DB_PASSWORD=...      # optional; defaults to DB_PASSWORD
```

## Project structure (summary)
```
backend/
  app/api              # chat, auth, reports, health
  app/services         # agents, KB processor, vector KB
  app/core             # config, DB connections
  scripts/             # init_db, build_knowledge_base, seeds
  data/vector_db       # ChromaDB storage
frontend/
  src/components       # chat UI
  src/services         # API client
```

## Licensing
Proprietary – internal project.
