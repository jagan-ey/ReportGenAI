# GenAI-Based Continuous Controls Monitoring (CCM) Platform - POC

A proof-of-concept implementation of a GenAI-driven Continuous Controls Monitoring platform for banking, featuring natural language query capabilities with 100% accuracy for predefined regulatory queries.

## 🎯 Overview

This POC demonstrates:
- **7 Predefined Control Questions** with 100% accuracy
- **8 BIU Star Schema Tables** with synthetic data
- **Natural Language to SQL** conversion using LangChain
- **No Vector DB** - Simplified architecture for POC
- **FastAPI Backend** with SQL agent
- **Synthetic Data Generation** for testing

## 📋 The 7 Control Questions

1. **ReKYC Freeze Control**: Customers whose ReKYC due >6 months, but ReKYC Credit freeze not applied under freeze code RKYCF?
2. **Mobile Number Duplication**: Customers having Single Mobile number updated in more than 10 ONI CIF IDs for Current Account?
3. **Gold Loan Tenure**: Tenure of more than 12 months for gold loan accounts under scheme code LRGMI for non-agricultural product variant with monthly interest payment?
4. **IEC Code Missing**: IEC code in CAGBL account not captured for Current Accounts?
5. **Gold Content Validation**: Customers having Gold Content in Mangalsutra is below 60% of Gross Weight?
6. **Mangalsutra Weight**: Customers having Mangalsutra is offered as a standalone jewellery, the net weight is less than 25gms?
7. **Tractor Loan Mapping**: Customers incorrectly mapped to Tractor loans (01,03 & 11 are eligible constitution code)?

## 🏗️ Architecture

```
┌─────────────────┐
│  React Frontend │  (To be implemented)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  FastAPI Backend│
│  - Chat API     │
│  - Query Router │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐ ┌──────────────┐
│Predefined│ │ LangChain   │
│Queries   │ │ SQL Agent   │
│(100% acc)│ │ (Ad-hoc)    │
└────┬───┘ └──────┬───────┘
     │           │
     └─────┬─────┘
           ▼
    ┌─────────────┐
    │ SQLite DB   │
    │ (8 Tables)  │
    └─────────────┘
```

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- OpenAI API Key
- (Optional) Node.js 18+ for frontend

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
# Create a local .env (this repo does not commit .env files)
# On Windows (PowerShell):
#   Copy-Item env.example .env
# On Mac/Linux:
#   cp env.example .env
#
# Edit `.env` and set Azure OpenAI + DB config (see env.example).

# Initialize database with synthetic data
python scripts/init_db.py

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

## 📊 Database Schema

The POC uses 8 BIU Star Schema tables:

1. **SUPER_CUSTOMER_DIM** - Customer master (100 records)
2. **CUSTOMER_NON_INDIVIDUAL_DIM** - Non-individual customers (100 records)
3. **ACCOUNT_CA_DIM** - Current accounts (150 records)
4. **SUPER_LOAN_DIM** - Loan master (200 records)
5. **SUPER_LOAN_ACCOUNT_DIM** - Loan details (200 records)
6. **CASELITE_LOAN_APPLICATIONS** - Gold loan apps (150 records)
7. **GOLD_COLLATERAL_DIM** - Gold collateral (150 records)
8. **CUSTOM_FREEZE_DETAILS_DIM** - Freeze details (variable)

## 🔑 Key Features

### 1. Predefined Query Routing (100% Accuracy)
- Keyword-based matching for 7 predefined questions
- Direct SQL execution (no LLM for predefined queries)
- Guaranteed accuracy for regulatory submissions

### 2. Ad-hoc Query Support
- LangChain SQL Agent for natural language queries
- Schema-aware SQL generation
- Query validation and safety checks

### 3. Synthetic Data
- Realistic relationships between tables
- Edge cases included for all 7 questions
- Sufficient data volume for meaningful results

## 📁 Project Structure

```
AxisGenAI/
├── backend/
│   ├── app/
│   │   ├── api/           # API endpoints
│   │   ├── core/          # Configuration, database, logging
│   │   ├── database/      # Schema and data generation
│   │   ├── services/      # Business logic (SQL agent, queries)
│   │   └── main.py        # FastAPI app
│   ├── scripts/
│   │   └── init_db.py     # Database initialization
│   └── requirements.txt
├── frontend/              # (To be implemented)
├── POC_REQUIREMENTS.md    # Detailed requirements
├── PROJECT_ANALYSIS.md    # Technical analysis
└── SETUP_GUIDE.md         # Setup instructions
```

## 🔒 Security & Compliance

- SQL injection prevention
- Query validation (SELECT only)
- Dangerous keyword blocking
- Audit logging (to be implemented)

## 📝 Next Steps

1. ✅ Database schema and synthetic data
2. ✅ Backend API with predefined queries
3. ✅ LangChain SQL agent integration
4. ⏳ React frontend chat interface
5. ⏳ Enhanced query matching (semantic similarity)
6. ⏳ Query result caching
7. ⏳ Performance monitoring

## 📚 Documentation

- [Setup Guide](SETUP_GUIDE.md) - Detailed setup instructions
- [POC Requirements](POC_REQUIREMENTS.md) - Question-to-table mapping
- [Project Analysis](PROJECT_ANALYSIS.md) - Technical architecture

## 🤝 Contributing

This is a POC for internal evaluation. For questions or issues, please refer to the project documentation.

## 📄 License

Proprietary - Axis Bank Internal Project
