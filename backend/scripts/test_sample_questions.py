"""
Test script to validate SQLMaker with 30 sample questions
Can be used for regression testing and validation
"""
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.services.sql_maker_agent import SQLMakerAgent
from app.core.database import get_db_url

# Sample questions from 30_SAMPLE_QUESTIONS.md
SAMPLE_QUESTIONS = [
    "Show me all gold loan accounts with LRGMI scheme that are disbursed",
    "How many small gold loans (SGL scheme) are currently active?",
    "List all medium gold loans (MGL) with tenure greater than 12 months",
    "What is the total loan amount for all LRGMI gold loans that are approved but not yet disbursed?",
    "Show me gold loan applications with non-agricultural product type and monthly installments",
    "Find all customers with ReKYC due date more than 6 months ago but no RKYCF freeze code",
    "Show me customers who have ReKYC due in the next 30 days",
    "List all accounts with RKYCF freeze that are still active",
    "How many customers have ReKYC overdue by more than 3 months?",
    "Show me all freeze codes and their counts across all accounts",
    "Find all Tractor loans where the customer constitution code is not eligible (not 01, 03, or 11)",
    "List all non-individual customers with constitution code 02 (Partnership)",
    "Show me customers with constitution code 11 (Sole Proprietorship) who have Tractor loans",
    "How many accounts belong to HUF (Hindu Undivided Family) customers?",
    "Find all customers with constitution code 04 (Private Limited Company) and their loan accounts",
    "Show me all Mangalsutra collaterals with gold content percentage less than 60%",
    "List Mangalsutra ornaments with net weight less than 25 grams",
    "What is the total collateral value for all gold chains?",
    "Show me all gold collaterals with 22K purity (91.67% or higher)",
    "Find all gold loan applications where the collateral net weight is less than 20 grams",
    "Show me all CAGBL accounts that are missing IEC codes in customer records",
    "List all current accounts with debit freeze flag set to true",
    "How many CAGBL accounts have a balance greater than 10 lakhs?",
    "Show me all accounts with scheme code CA001 (Standard Current Account)",
    "Find customers with IEC codes starting with 'IEC' and their account details",
    "Show me all mobile numbers that are used in more than 10 different CIFs",
    "List all CIFs sharing the same mobile number",
    "How many unique mobile numbers are there across all non-individual customers?",
    "Show me all Home Loan accounts with scheme HOUSING that are active",
    "List all Agricultural loans with scheme AGRI that have been disbursed"
]


def test_sqlmaker_questions():
    """Test SQLMaker with sample questions"""
    print("🧪 Testing SQLMaker with 30 Sample Questions")
    print("=" * 70)
    
    db_url = get_db_url()
    sqlmaker = SQLMakerAgent(db_url)
    
    results = {
        "total": len(SAMPLE_QUESTIONS),
        "success": 0,
        "failed": 0,
        "details": []
    }
    
    for i, question in enumerate(SAMPLE_QUESTIONS, 1):
        print(f"\n[{i}/{len(SAMPLE_QUESTIONS)}] Question: {question}")
        print("-" * 70)
        
        try:
            result = sqlmaker.generate_sql(question)
            
            if result.get("success"):
                sql = result.get("sql_query", "")
                attempt = result.get("attempt", 1)
                results["success"] += 1
                print(f"✅ SUCCESS (Attempt {attempt})")
                print(f"SQL: {sql[:200]}..." if len(sql) > 200 else f"SQL: {sql}")
                
                # Check if SQL uses domain knowledge (has valid values)
                uses_domain_knowledge = any([
                    "LRGMI" in sql or "SGL" in sql or "MGL" in sql,
                    "RKYCF" in sql,
                    "Tractor" in sql,
                    "Mangalsutra" in sql,
                    "CAGBL" in sql,
                    "HOUSING" in sql or "AGRI" in sql
                ])
                
                if uses_domain_knowledge:
                    print("   ✓ Uses domain knowledge (valid values detected)")
                else:
                    print("   ⚠️  May not be using domain knowledge")
                
                results["details"].append({
                    "question": question,
                    "status": "success",
                    "sql": sql,
                    "attempt": attempt,
                    "uses_domain_knowledge": uses_domain_knowledge
                })
            else:
                error = result.get("error", "Unknown error")
                sql = result.get("sql_query", "")
                results["failed"] += 1
                print(f"❌ FAILED: {error}")
                if sql:
                    print(f"SQL (partial): {sql[:200]}...")
                
                results["details"].append({
                    "question": question,
                    "status": "failed",
                    "error": error,
                    "sql": sql
                })
        except Exception as e:
            results["failed"] += 1
            print(f"❌ EXCEPTION: {str(e)}")
            results["details"].append({
                "question": question,
                "status": "exception",
                "error": str(e)
            })
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)
    print(f"Total Questions: {results['total']}")
    print(f"✅ Successful: {results['success']} ({results['success']/results['total']*100:.1f}%)")
    print(f"❌ Failed: {results['failed']} ({results['failed']/results['total']*100:.1f}%)")
    
    # Domain knowledge usage
    domain_usage = sum(1 for d in results["details"] if d.get("uses_domain_knowledge", False))
    if results["success"] > 0:
        print(f"📚 Using Domain Knowledge: {domain_usage}/{results['success']} ({domain_usage/results['success']*100:.1f}%)")
    
    # Failed questions
    if results["failed"] > 0:
        print("\n❌ Failed Questions:")
        for detail in results["details"]:
            if detail["status"] != "success":
                print(f"   - {detail['question']}")
                print(f"     Error: {detail.get('error', 'Unknown')}")
    
    return results


if __name__ == "__main__":
    try:
        test_sqlmaker_questions()
    except Exception as e:
        print(f"\n❌ Test script error: {e}")
        import traceback
        traceback.print_exc()

