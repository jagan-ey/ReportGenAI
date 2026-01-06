<<<<<<< HEAD
# GenAI-Based Continuous Controls Monitoring (CCM) Platform
=======
         # GenAI-Based Continuous Controls Monitoring (CCM) Platform - POC
>>>>>>> 1a8f6f02e09bcb7c778177a582167fce49731a15

An intelligent GenAI-driven Continuous Controls Monitoring platform for banking, featuring natural language query capabilities with LLM agents, vector knowledge base (RAG), and multi-agent orchestration for accurate SQL generation.

## 🎯 Overview

This platform provides:
- **Multi-Agent LLM System** - Orchestrator, SQLMaker, SQL Validator, FollowUp, and Conversational agents
- **Vector Knowledge Base (RAG)** - ChromaDB-based knowledge base with enriched domain knowledge
- **Saved Queries** - Predefined regulatory queries with 100% accuracy
- **Natural Language to SQL** - Intelligent SQL generation using Azure OpenAI (GPT-4o)
- **8 BIU Star Schema Tables** - Regulatory data mart with dimension tables
- **Separate Database Architecture** - Application database (ccm_genai) and Knowledge Base database (axis_reg_mart)
- **FastAPI Backend** - RESTful API with comprehensive agent orchestration
- **React Frontend** - Modern chat interface with real-time agent feedback

## 🤖 LLM Agents

The platform uses a multi-agent architecture:

1. **Orchestrator Agent** - Routes queries to appropriate agents (saved queries, SQL generation, or conversational)
2. **SQLMaker Agent** - Generates SQL queries from natural language using RAG knowledge base
3. **SQL Validator Agent** - Validates and corrects SQL queries (fallback when SQLMaker fails)
4. **FollowUp Agent** - Asks clarifying questions before query execution (date column selection, data freshness)
5. **Conversational Agent** - Handles non-data questions about the platform, schema, and capabilities

## 📊 Knowledge Base (RAG)

- **Vector Database**: ChromaDB for semantic search
- **Knowledge Sources**: Database schema, sample data, business documents (PDF, DOCX, TXT)
- **Enrichment**: LLM-generated business context, synonyms, valid values, relationships
- **Auto-updates**: Knowledge base can be rebuilt when regulatory data mart schema changes

## 🏗️ Architecture

```
┌─────────────────────┐
│  React Frontend     │
│  - Chat Interface   │
│  - Agent Badges     │
│  - Follow-up Q&A    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  FastAPI Backend    │
│  - Orchestrator     │
│  - Multi-Agent Sys  │
└──────────┬──────────┘
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
┌─────────┐  ┌──────────────────┐
│ SQLMaker│  │ SQL Validator    │
│ Agent   │  │ Agent (Fallback)  │
└────┬────┘  └────────┬──────────┘
     │                │
     ▼                ▼
┌─────────────────────────────┐
│  Vector Knowledge Base (RAG)│
│  - ChromaDB                 │
│  - Domain Knowledge          │
└──────────┬──────────────────┘
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
┌──────────┐  ┌──────────────┐
│ ccm_genai│  │axis_reg_mart │
│ (App DB) │  │ (KB/Data DB) │
│          │  │              │
│ - users  │  │ - 8 Dimension│
│ - saved  │  │   Tables     │
│   queries│  │              │
└──────────┘  └──────────────┘
```

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- SQL Server (with two databases: `ccm_genai` and `axis_reg_mart`)
- Azure OpenAI API Key and Endpoint
- Node.js 18+ for frontend
- ODBC Driver 17 for SQL Server

### Backend Setup

```bash
# Navigate to backend
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Set up environment
# Create a local .env file (this repo does not commit .env files)
# On Windows (PowerShell):
#   Copy-Item env.example .env
# On Mac/Linux:
#   cp env.example .env
#
# Edit `.env` and configure:
#   - Azure OpenAI settings (API key, endpoint, deployment)
#   - Main application database (DB_SERVER, DB_NAME=ccm_genai, DB_USERNAME, DB_PASSWORD)
#   - Knowledge base database (KB_DB_SERVER, KB_DB_NAME=axis_reg_mart, KB_DB_USERNAME, KB_DB_PASSWORD)
#   See env.example for all available settings.

# Initialize application database tables
python scripts/init_db.py

# (Optional) Build vector knowledge base from regulatory data mart
python scripts/build_knowledge_base.py

# Run server
uvicorn app.main:app --reload
```

### Test the API

```bash
# Health check
curl http://localhost:8000/api/health

# List predefined queries
curl http://localhost:8000/api/chat/predefined

# Test Question 1
curl -X POST http://localhost:8000/api/chat/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Customers whose ReKYC due >6 months, but ReKYC Credit freeze not applied under freeze code RKYCF?"}'
```

## 📊 Database Architecture

### Application Database (`ccm_genai`)
Stores application-specific data:
- **users** - User accounts and authentication
- **predefined_queries** - Saved queries (formerly predefined queries)
- **approval_requests** - Report approval workflow
- **scheduled_reports** - Scheduled report configurations

### Knowledge Base Database (`axis_reg_mart`)
Contains regulatory data mart with 8 dimension tables:
1. **SUPER_CUSTOMER_DIM** - Customer master
2. **CUSTOMER_NON_INDIVIDUAL_DIM** - Non-individual customers
3. **ACCOUNT_CA_DIM** - Current accounts
4. **SUPER_LOAN_DIM** - Loan master
5. **SUPER_LOAN_ACCOUNT_DIM** - Loan details
6. **CASELITE_LOAN_APPLICATIONS** - Gold loan applications
7. **GOLD_COLLATERAL_DIM** - Gold collateral
8. **CUSTOM_FREEZE_DETAILS_DIM** - Freeze details

**Note**: The knowledge base processor reads from `axis_reg_mart` to build the vector knowledge base (RAG).

## 🔑 Key Features

### 1. Multi-Agent LLM System
- **Orchestrator Agent**: Intelligent routing based on query type
- **SQLMaker Agent**: Generates SQL using RAG knowledge base
- **SQL Validator Agent**: Fallback correction when SQLMaker fails
- **FollowUp Agent**: Asks clarifying questions (date columns, data freshness)
- **Conversational Agent**: Answers questions about platform and schema

### 2. Vector Knowledge Base (RAG)
- **ChromaDB**: Semantic search for domain knowledge
- **Auto-enrichment**: LLM processes schema, data, and documents
- **Business context**: Synonyms, valid values, relationships, example queries
- **Maintenance**: Rebuild when regulatory data mart schema changes

### 3. Saved Queries (100% Accuracy)
- Predefined regulatory queries stored in database
- Intelligent matching with date/number threshold validation
- Direct SQL execution for guaranteed accuracy

### 4. Intelligent SQL Generation
- Schema-aware SQL generation using RAG
- Self-repair mechanism (2-pass generation)
- Post-execution query simplification
- Generic and schema-driven (no hardcoded values)

### 5. Query Safety & Validation
- SQL injection prevention
- SELECT-only queries
- Dangerous keyword blocking
- Schema validation before execution

## 📁 Project Structure

```
ccm-genai/
├── backend/
│   ├── app/
│   │   ├── api/              # API endpoints (chat, auth, reports, health)
│   │   ├── core/             # Configuration, database, logging
│   │   ├── database/         # Application schema (users, queries)
│   │   ├── models/           # User models (User, ApprovalRequest, ScheduledReport)
│   │   ├── services/         # LLM agents and business logic
│   │   │   ├── orchestrator_agent.py
│   │   │   ├── sql_maker_agent.py
│   │   │   ├── sql_validator_agent.py
│   │   │   ├── followup_agent.py
│   │   │   ├── conversational_agent.py
│   │   │   ├── knowledge_base_processor.py
│   │   │   └── vector_knowledge_base.py
│   │   └── main.py           # FastAPI app
│   ├── scripts/
│   │   ├── init_db.py        # Application database initialization
│   │   ├── build_knowledge_base.py  # Vector KB builder
│   │   └── seed_users.py     # User seeding
│   ├── data/
│   │   ├── vector_db/        # ChromaDB storage
│   │   └── business_docs/    # Business documents for KB
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/       # React components
│   │   ├── services/         # API services
│   │   └── contexts/         # Theme context
│   └── package.json
└── README.md
```

## 🔒 Security & Compliance

- SQL injection prevention
- Query validation (SELECT only)
- Dangerous keyword blocking
- Schema-driven validation (no hardcoded values)
- Separate database connections for app and data mart
- Environment-based configuration
- Audit logging

## 🚀 Environment Variables

Key environment variables (see `backend/env.example` for full list):

```env
# Azure OpenAI
AZURE_OPENAI_API_KEY=your_key
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2025-01-01-preview

# Main Application Database
DB_SERVER=your_server
DB_NAME=ccm_genai
DB_USERNAME=your_username
DB_PASSWORD=your_password

# Knowledge Base Database (Regulatory Data Mart)
KB_DB_SERVER=your_server  # Optional: defaults to DB_SERVER
KB_DB_NAME=axis_reg_mart
KB_DB_USERNAME=your_username  # Optional: defaults to DB_USERNAME
KB_DB_PASSWORD=your_password  # Optional: defaults to DB_PASSWORD
```

## 📚 Additional Documentation

- [Architecture Diagram](backend/ARCHITECTURE_DIAGRAM.md) - System and deployment architecture
- [Agent Architecture](backend/AGENT_ARCHITECTURE.md) - LLM agents and flow
- [Agent Comparison](backend/AGENT_COMPARISON.md) - SQLMaker vs SQL Validator
- [Vector KB Setup](backend/VECTOR_KNOWLEDGE_BASE_SETUP.md) - Knowledge base setup guide

## 🤝 Contributing

This is a POC for internal evaluation. For questions or issues, please refer to the project documentation.

## 📄 License

<<<<<<< HEAD
Proprietary - Internal Project
=======
Proprietary
>>>>>>> 1a8f6f02e09bcb7c778177a582167fce49731a15
