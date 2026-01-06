# GenAI Continuous Controls Monitoring (CCM) Platform

A GenAI-powered chat interface for banking controls monitoring that converts natural language queries into SQL using multi-agent LLMs, vector knowledge base (RAG), and strict database separation.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Architecture](#architecture)
- [Installation & Setup](#installation--setup)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [Development Workflow](#development-workflow)
- [Understanding the System](#understanding-the-system)
- [Troubleshooting](#troubleshooting)
- [Project Structure](#project-structure)
- [Environment Variables](#environment-variables)

## Overview

### What it does

- **Natural Language to SQL**: Converts user questions into SQL queries using Azure OpenAI (GPT-4o)
- **Dual Mode Operation**:
  - **Conversation Mode**: Answers questions using conversational agent (no SQL execution)
  - **Report Mode**: Generates and executes SQL queries on the knowledge base database
- **Multi-Agent System**: Intelligent routing through specialized agents (Orchestrator, SQLMaker, Validator, FollowUp, Conversational)
- **Vector Knowledge Base**: ChromaDB-powered RAG system enriched with database schema, sample data, and business documents
- **Saved Queries**: Predefined queries with guaranteed accuracy

### Key Features

- ✅ SELECT-only SQL generation (read-only safety)
- ✅ Schema-aware query generation
- ✅ Automatic SQL validation and error correction
- ✅ Follow-up questions for ambiguous queries
- ✅ Separate databases for application data vs. regulatory data
- ✅ Vector search for domain knowledge retrieval

## Prerequisites

Before you begin, ensure you have:

- **Python 3.10+** installed
- **Node.js 16+** and npm installed
- **SQL Server** (local or remote) with:
  - Application database (`ccm_genai`) - will be created automatically
  - Knowledge Base database (`regulatory_data_mart` or your custom name) - must exist with tables
- **Azure OpenAI** account with:
  - API key
  - Endpoint URL
  - GPT-4o deployment
- **ODBC Driver 17 for SQL Server** installed (for Windows) or `unixODBC` (for Linux/Mac)

### Verify Prerequisites

```bash
# Check Python version
python --version  # Should be 3.10+

# Check Node.js version
node --version    # Should be 16+

# Check npm
npm --version

# Verify SQL Server connection (Windows)
sqlcmd -S your_server -U your_username -Q "SELECT @@VERSION"
```

## Architecture

### High-Level Architecture

```
┌─────────────────┐
│  React Frontend │  ← Chat UI with mode toggle (Conversation/Report)
└────────┬────────┘
         │ HTTP/REST
┌────────▼────────────────────────┐
│     FastAPI Backend             │
│  ┌──────────────────────────┐  │
│  │   Orchestrator Agent     │  │  ← Routes queries to appropriate agent
│  └──────────┬───────────────┘  │
│             │                   │
│  ┌──────────▼───────────────┐  │
│  │   SQLMaker Agent        │  │  ← Generates SQL from natural language
│  │   SQL Validator Agent   │  │  ← Fixes SQL errors
│  │   FollowUp Agent        │  │  ← Asks clarifying questions
│  │   Conversational Agent  │  │  ← Handles non-SQL queries
│  └──────────┬───────────────┘  │
└─────────────┼──────────────────┘
              │
    ┌─────────┴─────────┐
    │                   │
┌───▼────────┐    ┌─────▼──────────────┐
│  App DB    │    │  KB DB             │
│ (ccm_genai)│    │ (regulatory_data)  │
│            │    │                    │
│ - users    │    │ - SUPER_CUSTOMER_  │
│ - queries  │    │   DIM              │
│ - reports  │    │ - SUPER_LOAN_      │
└────────────┘    │   ACCOUNT_DIM      │
                  │ - GOLD_COLLATERAL_ │
                  │   DIM              │
                  └────────────────────┘
                         │
                  ┌──────▼──────┐
                  │  ChromaDB   │  ← Vector knowledge base (RAG)
                  │  (Vector DB) │
                  └─────────────┘
```

### Database Architecture

The platform uses **two separate SQL Server databases**:

1. **Application DB (`ccm_genai`)**:
   - Stores application-specific data
   - Tables: `users`, `predefined_queries`, `approval_requests`, `scheduled_reports`
   - Created automatically via `scripts/init_db.py`
   - **Note**: This database is separate from the KB database, so its tables are never loaded into the KB

2. **Knowledge Base DB (`regulatory_data_mart`)**:
   - Contains regulatory/star-schema dimension tables
   - Examples: `SUPER_CUSTOMER_DIM`, `SUPER_LOAN_ACCOUNT_DIM`, `GOLD_COLLATERAL_DIM`
   - Used for SQL generation/execution and knowledge base building
   - **Must exist before running the application**

## Installation & Setup

### Step 1: Clone and Navigate

```bash
cd AxisGenAI  # or your project directory
```

### Step 2: Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
# source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

**Note**: If you encounter issues installing dependencies, ensure you have:
- Microsoft Visual C++ Build Tools (Windows)
- `python3-dev` and `build-essential` (Linux)

### Step 3: Frontend Setup

```bash
# Navigate to frontend directory (from project root)
cd frontend

# Install dependencies
npm install
```

### Step 4: Configure Environment Variables

1. Copy the example environment file:
   ```bash
   cd backend
   copy env.example .env  # Windows
   # cp env.example .env  # Linux/Mac
   ```

2. Edit `.env` file with your configuration (see [Configuration](#configuration) section below)

### Step 5: Initialize Application Database

```bash
cd backend
python scripts/init_db.py
```

This creates the `ccm_genai` database and all required tables.

### Step 6: Build Knowledge Base

```bash
cd backend
python scripts/build_knowledge_base.py
```

You'll be prompted with options:
1. **Full knowledge base** (schema + sample data + documents) - Recommended for first-time setup
2. **Schema only** - Fast setup, no sample data
3. **Schema + sample data** - Good balance
4. **Clear existing knowledge base** - For cleanup
5. **Show statistics** - View current KB stats

**Important**: Ensure your Knowledge Base database (`regulatory_data_mart`) exists and contains tables before running this script.

## Configuration

### Environment Variables

Create a `.env` file in the `backend` directory with the following variables:

```env
# ============================================
# Azure OpenAI Configuration
# ============================================
AZURE_OPENAI_API_KEY=your_api_key_here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2025-01-01-preview

# ============================================
# Application Database (ccm_genai)
# ============================================
DB_SERVER=your_sql_server_name
DB_NAME=ccm_genai
DB_USERNAME=your_db_username
DB_PASSWORD=your_db_password
DB_DRIVER=ODBC Driver 17 for SQL Server

# ============================================
# Knowledge Base Database (regulatory_data_mart)
# ============================================
# Optional: If not set, defaults to App DB settings
KB_DB_SERVER=your_sql_server_name          # Optional, defaults to DB_SERVER
KB_DB_NAME=regulatory_data_mart            # Your KB database name
KB_DB_USERNAME=your_db_username             # Optional, defaults to DB_USERNAME
KB_DB_PASSWORD=your_db_password             # Optional, defaults to DB_PASSWORD
KB_DB_DRIVER=ODBC Driver 17 for SQL Server

# ============================================
# Vector Knowledge Base (ChromaDB)
# ============================================
VECTOR_DB_PATH=data/vector_db               # Relative to backend directory
KNOWLEDGE_BASE_COLLECTION=ccm_knowledge_base

# ============================================
# Optional: BIU Contact Information
# ============================================
BIU_SPOC_NAME=BIU Support Team
BIU_SPOC_EMAIL=biu.support@bank.com
BIU_SPOC_PHONE=+91-22-2425-2525
BIU_SPOC_EXTENSION=Ext. 1234
```

### Configuration Tips

- **Database Connection**: Use Windows Authentication or SQL Server Authentication
- **KB Database**: Can be on the same server as App DB or different server
- **Vector DB Path**: Default is `data/vector_db` relative to `backend` directory
- **ODBC Driver**: Ensure the driver name matches your installed driver version

## Running the Application

### Start Backend Server

```bash
cd backend
# Ensure virtual environment is activated
uvicorn app.main:app --reload
```

The backend will start on `http://localhost:8000`

**Verify backend is running**:
- Open `http://localhost:8000/docs` for Swagger UI
- Open `http://localhost:8000/health` for health check

### Start Frontend Development Server

```bash
cd frontend
npm run dev
```

The frontend will start on `http://localhost:5173` (or another port if 5173 is busy)

### Access the Application

Open your browser and navigate to:
```
http://localhost:5173
```

## Development Workflow

### Typical Development Flow

1. **Make code changes** in `backend/app/` or `frontend/src/`
2. **Backend auto-reloads** (if using `--reload` flag)
3. **Frontend hot-reloads** automatically
4. **Test changes** in the browser

### Rebuilding Knowledge Base

After schema changes in your KB database:

```bash
cd backend
python scripts/build_knowledge_base.py
# Choose option 4 to clear, then option 1 to rebuild
```

### Viewing Logs

Backend logs appear in the terminal where `uvicorn` is running. For more detailed logging:

```bash
# Set log level in .env or config.py
LOG_LEVEL=DEBUG
```

### Testing SQL Generation

1. Start the application
2. Switch to **Report mode** in the chat UI
3. Ask questions like:
   - "How many active loans are there?"
   - "Show me all customers with overdue payments"
   - "List all NPA accounts"

### Debugging Tips

- **SQL Errors**: Check backend terminal for full error messages
- **Agent Routing**: Look for agent badges in chat UI to see which agent handled the query
- **Knowledge Base**: Use `build_knowledge_base.py` option 5 to view KB statistics
- **Database Connection**: Test with `sqlcmd` or SSMS before running the app

## Understanding the System

### Agent Flow

```
User Query
    │
    ▼
┌─────────────────┐
│  Orchestrator   │  ← Decides: predefined query, SQL generation, or conversational?
└────────┬────────┘
         │
    ┌────┴────┬──────────────┐
    │         │              │
    ▼         ▼              ▼
Predefined  SQLMaker    Conversational
Query       Agent       Agent
    │         │              │
    │         ▼              │
    │    FollowUp?          │
    │    (if ambiguous)     │
    │         │              │
    │         ▼              │
    │    SQL Execution       │
    │         │              │
    │         ▼              │
    │    Validator?          │
    │    (if error)          │
    │         │              │
    └─────────┴──────────────┘
              │
              ▼
         Response to User
```

### Knowledge Base Building Process

1. **Schema Introspection**: Reads table/column definitions from KB database
   - Uses `get_kb_engine()` which connects to the KB database (not the app database)
2. **LLM Enrichment**: Adds business descriptions, synonyms, relationships
3. **Sample Data**: Optionally includes value patterns from actual data
4. **Document Ingestion**: Processes PDF/DOCX/TXT business documents
5. **Chunking**: Splits content into manageable chunks
6. **Embedding**: Generates vector embeddings using SentenceTransformers
7. **Storage**: Stores in ChromaDB for semantic search

### Query Processing Flow

1. **User submits query** in Report mode
2. **Orchestrator** checks if it matches a predefined query
3. If not, **SQLMaker** retrieves relevant schema from vector KB
4. **SQLMaker** generates SQL using LLM with schema context
5. **FollowUp agent** may ask clarifying questions if ambiguous
6. **SQL executed** on KB database
7. If error, **SQL Validator** attempts to fix the query
8. **Results returned** to user

## Troubleshooting

### Common Issues

#### 1. Database Connection Errors

**Error**: `[Microsoft][ODBC Driver 17 for SQL Server][SQL Server]Login failed`

**Solutions**:
- Verify SQL Server is running
- Check username/password in `.env`
- Ensure SQL Server allows SQL authentication (if not using Windows auth)
- Test connection with `sqlcmd`:
  ```bash
  sqlcmd -S your_server -U your_username -P your_password
  ```

#### 2. ODBC Driver Not Found

**Error**: `[Microsoft][ODBC Driver Manager] Data source name not found`

**Solutions**:
- Install ODBC Driver 17 for SQL Server
- Verify driver name in `.env` matches installed driver
- List available drivers:
  ```bash
  # Windows PowerShell
  Get-OdbcDriver | Select-Object Name
  ```

#### 3. Knowledge Base Build Fails

**Error**: `Could not parse JSON response` or `NoneType object has no attribute`

**Solutions**:
- Ensure Azure OpenAI credentials are correct
- Check internet connection
- Verify KB database exists and has tables
- Try clearing KB first (option 4), then rebuilding

#### 4. Vector DB File Lock Errors (Windows)

**Error**: `[WinError 32] The process cannot access the file`

**Solutions**:
- Close any applications using ChromaDB files
- Stop the backend server
- Use `build_knowledge_base.py` option 4 → option 2 (delete files)
- Restart backend

#### 5. Frontend Can't Connect to Backend

**Error**: `Network Error` or `CORS error`

**Solutions**:
- Verify backend is running on `http://localhost:8000`
- Check `CORS_ORIGINS` in backend config
- Ensure frontend is using correct API URL in `src/services/api.js`

#### 6. SQL Generation Uses Wrong Tables

**Issue**: SQLMaker generates queries with non-existent tables

**Solutions**:
- Rebuild knowledge base to include latest schema
- Verify KB database has the expected tables
- Check that table names in KB match actual database tables

#### 7. Import Errors

**Error**: `ModuleNotFoundError: No module named 'chromadb'`

**Solutions**:
- Ensure virtual environment is activated
- Reinstall dependencies: `pip install -r requirements.txt`
- Check Python version (3.10+)

### Getting Help

- Check backend logs in terminal
- Review error messages in browser console (F12)
- Verify all environment variables are set correctly
- Ensure all prerequisites are installed

## Project Structure

```
AxisGenAI/
├── backend/
│   ├── app/
│   │   ├── api/                    # API endpoints
│   │   │   ├── chat.py             # Main chat endpoint
│   │   │   ├── auth.py             # Authentication
│   │   │   └── reports.py          # Report management
│   │   ├── services/               # Business logic
│   │   │   ├── sql_maker_agent.py  # SQL generation agent
│   │   │   ├── sql_validator_agent.py  # SQL validation agent
│   │   │   ├── followup_agent.py   # Follow-up questions agent
│   │   │   ├── orchestrator_agent.py  # Query routing agent
│   │   │   ├── conversational_agent.py  # Conversational agent
│   │   │   ├── knowledge_base_processor.py  # KB building logic
│   │   │   ├── vector_knowledge_base.py  # ChromaDB wrapper
│   │   │   └── predefined_queries_db.py  # Saved queries
│   │   ├── core/
│   │   │   ├── config.py           # Configuration settings
│   │   │   └── database.py         # Database connections
│   │   └── main.py                 # FastAPI app entry point
│   ├── scripts/
│   │   ├── init_db.py              # Initialize app database
│   │   └── build_knowledge_base.py # Build vector KB
│   ├── data/
│   │   ├── vector_db/              # ChromaDB storage (created automatically)
│   │   └── business_docs/          # Optional: PDF/DOCX/TXT documents
│   ├── requirements.txt            # Python dependencies
│   ├── env.example                 # Environment variables template
│   └── .env                        # Your environment variables (create this)
│
└── frontend/
    ├── src/
    │   ├── components/
    │   │   └── ChatInterface.jsx   # Main chat UI component
    │   ├── services/
    │   │   └── api.js              # API client
    │   └── App.jsx                 # React app entry
    ├── package.json               # Node dependencies
    └── vite.config.js             # Vite configuration
```

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key | `abc123...` |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL | `https://your-resource.openai.azure.com/` |
| `AZURE_OPENAI_CHAT_DEPLOYMENT` | Deployment name for chat model | `gpt-4o` |
| `DB_SERVER` | SQL Server hostname | `localhost` or `server\instance` |
| `DB_NAME` | Application database name | `ccm_genai` |
| `DB_USERNAME` | Database username | `sa` or `your_user` |
| `DB_PASSWORD` | Database password | `your_password` |
| `KB_DB_NAME` | Knowledge Base database name | `regulatory_data_mart` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `KB_DB_SERVER` | KB database server (if different) | Uses `DB_SERVER` |
| `KB_DB_USERNAME` | KB database username (if different) | Uses `DB_USERNAME` |
| `KB_DB_PASSWORD` | KB database password (if different) | Uses `DB_PASSWORD` |
| `VECTOR_DB_PATH` | Path to ChromaDB storage | `data/vector_db` |
| `KNOWLEDGE_BASE_COLLECTION` | ChromaDB collection name | `ccm_knowledge_base` |
| `BIU_SPOC_EMAIL` | BIU support email | `biu.support@bank.com` |

---

## Quick Reference

### Essential Commands

```bash
# Backend setup
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt

# Initialize database
python scripts/init_db.py

# Build knowledge base
python scripts/build_knowledge_base.py

# Run backend
uvicorn app.main:app --reload

# Frontend setup
cd frontend
npm install
npm run dev
```

### Useful URLs

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/health`

---

**Licensing**: Proprietary – internal project.
