"""
Test Enhanced SQLMaker with RAG Knowledge Base
Tests SQLMaker's ability to generate SQL using domain knowledge
"""
import sys
import os

# Get the backend directory (parent of scripts/)
script_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(script_dir)
project_root = os.path.dirname(backend_dir)

# Add backend to Python path
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Change working directory to backend for relative imports
os.chdir(backend_dir)

from app.core.config import settings
from app.core.database import get_db_url
from app.services.sql_maker_agent import SQLMakerAgent


def test_question(agent: SQLMakerAgent, question: str, expected_keywords: list = None):
    """Test a single question and display results"""
    print(f"\n{'='*80}")
    print(f"❓ Question: {question}")
    print(f"{'='*80}")
    
    result = agent.generate_sql(question)
    
    if result.get("success"):
        sql = result.get("sql_query", "")
        attempt = result.get("attempt", 1)
        print(f"✅ Success (Attempt {attempt})")
        print(f"\n📝 Generated SQL:")
        print(f"{sql}\n")
        
        # Check for expected keywords
        if expected_keywords:
            sql_upper = sql.upper()
            found = []
            missing = []
            for keyword in expected_keywords:
                if keyword.upper() in sql_upper:
                    found.append(keyword)
                else:
                    missing.append(keyword)
            
            if found:
                print(f"✓ Found expected keywords: {', '.join(found)}")
            if missing:
                print(f"⚠️  Missing expected keywords: {', '.join(missing)}")
    else:
        error = result.get("error", "Unknown error")
        sql = result.get("sql_query")
        print(f"❌ Failed: {error}")
        if sql:
            print(f"\n📝 Generated SQL (invalid):")
            print(f"{sql}\n")


def main():
    """Run test suite"""
    print("🧪 Testing Enhanced SQLMaker with RAG Knowledge Base")
    print("=" * 80)
    
    # Initialize SQLMaker agent
    db_url = get_db_url()
    agent = SQLMakerAgent(db_url)
    
    # Test questions that require domain knowledge
    test_cases = [
        {
            "question": "Show me all gold loan accounts with LRGMI scheme that are disbursed",
            "expected_keywords": ["LRGMI", "DISBURSED", "caselite_loan_applications"],
            "description": "Tests knowledge of LRGMI scheme and DISBURSED status"
        },
        {
            "question": "Find customers with ReKYC due more than 6 months ago but no RKYCF freeze",
            "expected_keywords": ["RE_KYC_DUE_DATE", "RKYCF", "super_customer_dim", "custom_freeze_details_dim"],
            "description": "Tests knowledge of ReKYC compliance and RKYCF freeze code"
        },
        {
            "question": "List all Mangalsutra collaterals with gold content less than 60%",
            "expected_keywords": ["Mangalsutra", "PERCENTAGE", "gold_collateral_dim", "< 60"],
            "description": "Tests knowledge of ornament types and gold purity rules"
        },
        {
            "question": "Show me Tractor loans with wrong constitution code",
            "expected_keywords": ["Tractor", "CONSTITUTION_CODE", "super_loan_dim"],
            "description": "Tests knowledge of Tractor loan eligibility rules"
        },
        {
            "question": "Count all SGL gold loans that are approved",
            "expected_keywords": ["SGL", "APPROVED", "caselite_loan_applications"],
            "description": "Tests knowledge of SGL scheme and APPROVED status"
        },
        {
            "question": "Find CAGBL accounts without IEC codes",
            "expected_keywords": ["CAGBL", "IEC", "account_ca_dim", "customer_non_individual_dim"],
            "description": "Tests knowledge of CAGBL scheme and IEC code relationship"
        },
        {
            "question": "Show me all non-agricultural loans with MGL scheme",
            "expected_keywords": ["non-agricultural", "MGL", "caselite_loan_applications"],
            "description": "Tests knowledge of product categories and scheme matching"
        },
        {
            "question": "List gold loan applications with tenure greater than 12 months and monthly installments",
            "expected_keywords": ["TENURE", "monthly", "INSTALTYPE", "> 12"],
            "description": "Tests knowledge of loan tenure and installment types"
        }
    ]
    
    print(f"\n📋 Running {len(test_cases)} test cases...\n")
    
    passed = 0
    failed = 0
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🔍 Test Case {i}/{len(test_cases)}: {test_case['description']}")
        test_question(agent, test_case["question"], test_case.get("expected_keywords"))
        
        # Simple pass/fail check
        result = agent.generate_sql(test_case["question"])
        if result.get("success"):
            passed += 1
        else:
            failed += 1
    
    # Summary
    print(f"\n{'='*80}")
    print(f"📊 Test Summary")
    print(f"{'='*80}")
    print(f"✅ Passed: {passed}/{len(test_cases)}")
    print(f"❌ Failed: {failed}/{len(test_cases)}")
    print(f"📈 Success Rate: {(passed/len(test_cases)*100):.1f}%")
    print(f"\n💡 Note: These tests verify SQL generation. Check the SQL queries above")
    print(f"   to ensure they use correct domain values (LRGMI, SGL, MGL, etc.)")
    print(f"   and follow business rules from the knowledge base.")


if __name__ == "__main__":
    main()

