"""
Predefined SQL queries for the 7 POC questions
Ensures 100% accuracy for regulatory queries
"""
from typing import Dict, Optional
from datetime import datetime, timedelta

PREDEFINED_QUERIES = {
    # Question 1: ReKYC Freeze Control
    "rekyc_freeze": {
        "question": "Customers whose ReKYC due >6 months, but ReKYC Credit freeze not applied under freeze code RKYCF?",
        "sql": """
        SELECT DISTINCT 
            sc.CUST_ID,
            sc.CUST_NAME,
            sc.RE_KYC_DUE_DATE,
            sc.CLEAN_MOBILE,
            sc.PRIMARY_SOL_ID,
            sc.STATE,
            sc.CITY
        FROM super_customer_dim sc
        LEFT JOIN custom_freeze_details_dim cfd 
            ON sc.CUST_ID = cfd.CUST_ID 
            AND cfd.FREZ_CODE = 'RKYCF'
            AND (cfd.UNFREZ_FLG IS NULL OR cfd.UNFREZ_FLG != 'Y')
        WHERE sc.RE_KYC_DUE_DATE < DATEADD(MONTH, -6, GETDATE())
            AND cfd.FREZ_CODE IS NULL
            AND sc.STATUS = 'ACTIVE'
        ORDER BY sc.RE_KYC_DUE_DATE ASC
        """,
        "description": "Find customers with ReKYC due date more than 6 months ago who don't have RKYCF freeze code applied"
    },
    
    # Question 2: Mobile Number Duplication
    "mobile_duplication": {
        "question": "Customers having Single Mobile number updated in more than 10 ONI CIF IDs (i.e. partnership and above) for Current Account?",
        "sql": """
        SELECT 
            cni.PHONE_NUMBER,
            COUNT(DISTINCT cni.CIF_ID) as cif_count,
            STUFF((
                SELECT DISTINCT ', ' + CAST(cni2.CIF_ID AS VARCHAR(50))
                FROM customer_non_individual_dim cni2
                WHERE cni2.PHONE_NUMBER = cni.PHONE_NUMBER
                FOR XML PATH(''), TYPE
            ).value('.', 'NVARCHAR(MAX)'), 1, 2, '') as cif_ids,
            STUFF((
                SELECT DISTINCT ', ' + CAST(ca2.ACCT_NUM AS VARCHAR(50))
                FROM account_ca_dim ca2
                INNER JOIN customer_non_individual_dim cni3 ON ca2.CUST_ID = cni3.CUST_ID
                WHERE cni3.PHONE_NUMBER = cni.PHONE_NUMBER
                    AND ca2.ACCT_STATUS = 'ACTIVE'
                FOR XML PATH(''), TYPE
            ).value('.', 'NVARCHAR(MAX)'), 1, 2, '') as account_numbers
        FROM customer_non_individual_dim cni
        INNER JOIN account_ca_dim ca ON cni.CUST_ID = ca.CUST_ID
        WHERE cni.CONSTITUTION_CODE IN ('01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20')
            AND cni.PHONE_NUMBER IS NOT NULL
            AND ca.ACCT_STATUS = 'ACTIVE'
        GROUP BY cni.PHONE_NUMBER
        HAVING COUNT(DISTINCT cni.CIF_ID) > 10
        ORDER BY cif_count DESC
        """,
        "description": "Find mobile numbers used in more than 10 non-individual customer CIFs for current accounts"
    },
    
    # Question 3: Gold Loan Tenure
    "gold_loan_tenure": {
        "question": "Tenure of more than 12 months for gold loan accounts under scheme code LRGMI for non-agricultural product variant with a monthly interest payment structure?",
        "sql": """
        SELECT 
            cla.APP_ID,
            cla.FIN_LOAN_ACCOUNT_NUMBER,
            cla.SCHEME_NAME,
            cla.PRODUCT,
            cla.TENURE,
            cla.AGREED_LN_AMT,
            cla.LENDING_RATE,
            sla.INSTALTYPE,
            sla.ACCNO,
            sla.CUSTID,
            sla.NAME
        FROM caselite_loan_applications cla
        INNER JOIN super_loan_account_dim sla 
            ON cla.FIN_LOAN_ACCOUNT_NUMBER = sla.ACCNO
        WHERE cla.SCHEME_NAME = 'LRGMI'
            AND cla.PRODUCT = 'non-agricultural'
            AND cla.TENURE > 12
            AND sla.INSTALTYPE = 'monthly'
            AND cla.ACTIVE_IND = 'Y'
        ORDER BY cla.TENURE DESC
        """,
        "description": "Find gold loan accounts with LRGMI scheme, non-agricultural product, tenure > 12 months, and monthly payment"
    },
    
    # Question 4: IEC Code Missing
    "iec_code_missing": {
        "question": "IEC code in CAGBL account not captured for Current Accounts?",
        "sql": """
        SELECT 
            ca.ACCT_NUM,
            ca.ACCT_NAME,
            ca.SCHEME_CODE,
            ca.SCHEME_DESC,
            cni.CUST_ID,
            cni.CIF_ID,
            cni.CUST_NAME,
            cni.IEC,
            ca.ACCT_OPN_DATE,
            ca.ACCT_STATUS,
            ca.SOL_ID
        FROM account_ca_dim ca
        INNER JOIN customer_non_individual_dim cni ON ca.CUST_ID = cni.CUST_ID
        WHERE ca.SCHEME_CODE = 'CAGBL'
            AND (cni.IEC IS NULL OR cni.IEC = '')
            AND ca.ACCT_STATUS = 'ACTIVE'
        ORDER BY ca.ACCT_OPN_DATE DESC
        """,
        "description": "Find CAGBL current accounts where IEC code is missing for non-individual customers"
    },
    
    # Question 5: Gold Content Validation
    "gold_content_validation": {
        "question": "Customers having Gold Content in Mangalsutra is below 60% of Gross Weight?",
        "sql": """
        SELECT 
            gcd.APP_ID,
            gcd.ACCOUNT_NUMBER,
            gcd.ORNAMENT_TYPE,
            gcd.GROSS_WT,
            gcd.NET_WT,
            gcd.PERCENTAGE,
            (gcd.PERCENTAGE * gcd.GROSS_WT / 100) as gold_content_weight,
            (0.6 * gcd.GROSS_WT) as required_min_gold_weight,
            gcd.LOAN_VALUE,
            gcd.COLLATERAL_VALUE,
            gcd.SOL_ID
        FROM gold_collateral_dim gcd
        WHERE gcd.ORNAMENT_TYPE = 'Mangalsutra'
            AND gcd.PERCENTAGE < 60
        ORDER BY gcd.PERCENTAGE ASC
        """,
        "description": "Find Mangalsutra ornaments where gold percentage is below 60% of gross weight"
    },
    
    # Question 6: Mangalsutra Weight
    "mangalsutra_weight": {
        "question": "Customers having Mangalsutra is offered as a standalone jewellery, the net weight is less than 25gms?",
        "sql": """
        SELECT 
            gcd.APP_ID,
            gcd.ACCOUNT_NUMBER,
            gcd.ORNAMENT_TYPE,
            gcd.GROSS_WT,
            gcd.NET_WT,
            gcd.PERCENTAGE,
            gcd.NO_UNITS,
            gcd.LOAN_VALUE,
            gcd.COLLATERAL_VALUE,
            gcd.SOL_ID
        FROM gold_collateral_dim gcd
        WHERE gcd.ORNAMENT_TYPE = 'Mangalsutra'
            AND gcd.NET_WT < 25
            AND gcd.NO_UNITS = 1
        ORDER BY gcd.NET_WT ASC
        """,
        "description": "Find standalone Mangalsutra (single unit) with net weight less than 25 grams"
    },
    
    # Question 7: Tractor Loan Mapping
    "tractor_loan_mapping": {
        "question": "Customers incorrectly mapped to Tractor loans (01,03 & 11 are eligible constitution code for Tractor loan)?",
        "sql": """
        SELECT 
            sl.ACCNO,
            sl.CUSTID,
            sl.NAME,
            sl.PRODUCT_ID,
            sl.DESCRIPTION,
            cni.CIF_ID,
            cni.CUST_NAME,
            cni.CONSTITUTION_CODE,
            cni.CONSTITUTION_DESC,
            sl.ACCT_OPN_DATE,
            sl.BALANCE,
            sl.SANCT_LIM,
            sl.SOL_ID
        FROM super_loan_dim sl
        INNER JOIN customer_non_individual_dim cni ON sl.CUSTID = cni.CUST_ID
        WHERE sl.PRODUCT_ID = 'Tractor'
            AND cni.CONSTITUTION_CODE NOT IN ('01', '03', '11')
        ORDER BY sl.ACCT_OPN_DATE DESC
        """,
        "description": "Find Tractor loans where customer constitution code is not 01, 03, or 11 (ineligible)"
    }
}


def get_predefined_query(question_key: str) -> Optional[Dict]:
    """Get predefined query by key"""
    return PREDEFINED_QUERIES.get(question_key)


def match_question_to_predefined(user_question: str) -> Optional[str]:
    """
    Strict keyword matching to identify predefined questions
    Only matches if the question closely matches the predefined query
    """
    user_lower = user_question.lower().strip()
    
    # Question 1: ReKYC - must have both "rekyc" and "rkycf" or "freeze"
    if "rekyc" in user_lower and ("rkycf" in user_lower or ("freeze" in user_lower and "6" in user_lower)):
        return "rekyc_freeze"
    
    # Question 2: Mobile duplication - must have "10" or "ten" and "cif"
    if ("mobile" in user_lower or "phone" in user_lower) and ("10" in user_lower or "ten" in user_lower) and "cif" in user_lower:
        return "mobile_duplication"
    
    # Question 3: Gold loan tenure - must have "lrgmi", "12", and "non-agricultural"
    if "lrgmi" in user_lower and ("12" in user_lower or "twelve" in user_lower) and "non-agricultural" in user_lower:
        return "gold_loan_tenure"
    
    # Question 4: IEC code - must have both "iec" and "cagbl"
    if "iec" in user_lower and "cagbl" in user_lower:
        return "iec_code_missing"
    
    # Question 5: Gold content - must have "mangalsutra", "60", and "percentage" or "gold content"
    if "mangalsutra" in user_lower and ("60" in user_lower or "sixty" in user_lower) and ("percentage" in user_lower or "gold content" in user_lower):
        return "gold_content_validation"
    
    # Question 6: Mangalsutra weight - must have "mangalsutra", "25", and "weight" or "gms"
    if "mangalsutra" in user_lower and ("25" in user_lower or "twenty" in user_lower) and ("weight" in user_lower or "gms" in user_lower):
        return "mangalsutra_weight"
    
    # Question 7: Tractor loan - STRICT: must have "tractor", "constitution", AND all three codes "01", "03", "11"
    # This ensures it only matches the exact predefined question
    # If user asks with different codes (e.g., only "01 & 11" without "03"), it won't match and will use LLM
    if ("tractor" in user_lower and "constitution" in user_lower and 
        "01" in user_lower and "03" in user_lower and "11" in user_lower):
        # Double-check: ensure all three codes are explicitly mentioned
        # This prevents matching if user asks with only "01 & 11"
        return "tractor_loan_mapping"
    
    return None

