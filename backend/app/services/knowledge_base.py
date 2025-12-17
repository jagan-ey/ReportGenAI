"""
RAG Knowledge Base for SQLMaker Agent

Provides domain knowledge about:
- Column definitions and business meanings
- Valid values for each column
- Business rules and relationships
- Example queries and patterns
"""

from typing import Dict, List, Optional
import json
import os

# Domain Knowledge - Column Definitions and Valid Values
COLUMN_DEFINITIONS = {
    "caselite_loan_applications": {
        "SCHEME_NAME": {
            "description": "Loan scheme name. Identifies the specific loan program or initiative.",
            "valid_values": [
                {"value": "LRGMI", "meaning": "Large Gold Loan Microfinance Initiative - for large gold loans"},
                {"value": "SGL", "meaning": "Small Gold Loan - for small gold loan amounts"},
                {"value": "MGL", "meaning": "Medium Gold Loan - for medium gold loan amounts"},
                {"value": "AGRI", "meaning": "Agricultural Loan Scheme - for agricultural/farming loans"},
                {"value": "MSME", "meaning": "Micro, Small & Medium Enterprise - for MSME business loans"},
                {"value": "PRI", "meaning": "Priority Sector Loan - priority sector lending"},
                {"value": "RETAIL", "meaning": "Retail Loan Scheme - general retail loans"},
                {"value": "HOUSING", "meaning": "Housing Loan Scheme - for home loans"},
                {"value": "EDU", "meaning": "Education Loan Scheme - for education loans"},
                {"value": "VEHICLE", "meaning": "Vehicle Loan Scheme - for vehicle loans"}
            ],
            "business_rules": [
                "LRGMI, SGL, MGL are typically used with PRODUCT='non-agricultural' and Gold Loan products",
                "AGRI and PRI are used with PRODUCT='agricultural'",
                "HOUSING is used with Home Loan products",
                "EDU is used with Education Loan products",
                "VEHICLE is used with Car Loan and Two-Wheeler Loan products"
            ]
        },
        "PRODUCT": {
            "description": "Product category classification. NOTE: This table has PRODUCT (not PRODUCT_ID). super_loan_dim and super_loan_account_dim have PRODUCT_ID (not PRODUCT).",
            "valid_values": [
                {"value": "non-agricultural", "meaning": "Non-agricultural loans (Gold, Personal, Home, Car, Business, etc.)"},
                {"value": "agricultural", "meaning": "Agricultural loans (Tractor, Farming, etc.)"},
                {"value": "commercial", "meaning": "Commercial/Business loans"}
            ],
            "business_rules": [
                "non-agricultural includes: Gold Loan, Personal Loan, Home Loan, Car Loan, Business Loan, Education Loan",
                "agricultural includes: Tractor Loan, Agricultural Loan",
                "commercial includes: Business Loan, MSME Loan"
            ]
        },
        "STAGE_STATUS": {
            "description": "Current status of the loan application",
            "valid_values": [
                {"value": "APPROVED", "meaning": "Application has been approved"},
                {"value": "PENDING", "meaning": "Application is pending review"},
                {"value": "DISBURSED", "meaning": "Loan has been disbursed to customer"},
                {"value": "REJECTED", "meaning": "Application has been rejected"},
                {"value": "CANCELLED", "meaning": "Application was cancelled"},
                {"value": "ON_HOLD", "meaning": "Application is on hold"}
            ]
        }
    },
    "super_loan_dim": {
        "PRODUCT_ID": {
            "description": "Type of loan product (NOT 'PRODUCT' - column name is PRODUCT_ID)",
            "valid_values": [
                {"value": "Gold Loan", "meaning": "Loan against gold collateral"},
                {"value": "Personal Loan", "meaning": "Unsecured personal loan"},
                {"value": "Home Loan", "meaning": "Loan for purchasing/constructing home"},
                {"value": "Car Loan", "meaning": "Loan for purchasing car"},
                {"value": "Tractor Loan", "meaning": "Loan for purchasing tractor (agricultural)"},
                {"value": "Agricultural Loan", "meaning": "General agricultural/farming loan"},
                {"value": "Business Loan", "meaning": "Loan for business purposes"},
                {"value": "Education Loan", "meaning": "Loan for education expenses"},
                {"value": "Two-Wheeler Loan", "meaning": "Loan for purchasing two-wheeler"}
            ],
            "business_rules": [
                "Column name is PRODUCT_ID (not PRODUCT)",
                "Tractor Loan and Agricultural Loan are agricultural products",
                "Tractor Loan is only eligible for constitution codes: 01 (Individual), 03 (HUF), 11 (Sole Proprietorship)",
                "Gold Loan typically uses schemes: LRGMI, SGL, MGL",
                "Home Loan typically uses scheme: HOUSING",
                "Education Loan typically uses scheme: EDU",
                "Car Loan and Two-Wheeler Loan typically use scheme: VEHICLE"
            ]
        },
        "SCHEME": {
            "description": "Loan scheme identifier (NOT 'SCHEME_NAME' - column name is SCHEME)",
            "valid_values": [
                {"value": "LRGMI", "meaning": "Large Gold Loan Microfinance Initiative"},
                {"value": "SGL", "meaning": "Small Gold Loan"},
                {"value": "MGL", "meaning": "Medium Gold Loan"},
                {"value": "AGRI", "meaning": "Agricultural Loan Scheme"},
                {"value": "PRI", "meaning": "Priority Sector Loan"},
                {"value": "HOUSING", "meaning": "Housing Loan Scheme"},
                {"value": "EDU", "meaning": "Education Loan Scheme"},
                {"value": "VEHICLE", "meaning": "Vehicle Loan Scheme"},
                {"value": "RETAIL", "meaning": "Retail Loan Scheme"},
                {"value": "MSME", "meaning": "MSME Loan Scheme"}
            ],
            "business_rules": [
                "Column name is SCHEME (not SCHEME_NAME)",
                "Note: caselite_loan_applications has SCHEME_NAME (different column name)"
            ]
        },
        "important_note": "super_loan_dim does NOT have: TENURE, INSTALTYPE, SCHEME_NAME, or PRODUCT. Use super_loan_account_dim for TENURE and INSTALTYPE. Use caselite_loan_applications for SCHEME_NAME and PRODUCT."
    },
    "super_loan_account_dim": {
        "SCHEME": {
            "description": "Loan scheme identifier (same as super_loan_dim.SCHEME). Contains scheme codes like 'LRGMI', 'SGL', 'MGL'. PREFER using this column directly instead of joining with caselite_loan_applications.SCHEME_NAME when possible.",
            "valid_values": [
                {"value": "LRGMI", "meaning": "Large Gold Loan Microfinance Initiative"},
                {"value": "SGL", "meaning": "Small Gold Loan"},
                {"value": "MGL", "meaning": "Medium Gold Loan"},
                {"value": "AGRI", "meaning": "Agricultural Loan Scheme"},
                {"value": "PRI", "meaning": "Priority Sector Loan"},
                {"value": "HOUSING", "meaning": "Housing Loan Scheme"},
                {"value": "EDU", "meaning": "Education Loan Scheme"},
                {"value": "VEHICLE", "meaning": "Vehicle Loan Scheme"},
                {"value": "RETAIL", "meaning": "Retail Loan Scheme"},
                {"value": "MSME", "meaning": "MSME Loan Scheme"}
            ],
            "business_rules": [
                "super_loan_account_dim.SCHEME contains the same scheme codes as caselite_loan_applications.SCHEME_NAME",
                "If query only needs scheme code (like 'LRGMI'), use super_loan_account_dim.SCHEME directly - no need to join with caselite_loan_applications",
                "Only join with caselite_loan_applications if you need columns that ONLY exist there (like STAGE_STATUS, APPLIED_DATE_LED)"
            ]
        },
        "PRODUCT_ID": {
            "description": "Type of loan product (same as super_loan_dim.PRODUCT_ID). Contains product types like 'Gold Loan', 'Tractor', etc.",
            "valid_values": "See super_loan_dim.PRODUCT_ID"
        },
        "INSTALTYPE": {
            "description": "Installment payment frequency (NOT 'INTEREST_PAYMENT_STRUCTURE'). Column name is INSTALTYPE.",
            "valid_values": [
                {"value": "monthly", "meaning": "Monthly installments"},
                {"value": "quarterly", "meaning": "Quarterly installments"},
                {"value": "yearly", "meaning": "Yearly installments"}
            ],
            "business_rules": [
                "Column name is INSTALTYPE (not INTEREST_PAYMENT_STRUCTURE or PAYMENT_STRUCTURE)",
                "Use INSTALTYPE = 'monthly' for monthly payment structure",
                "Use INSTALTYPE = 'quarterly' for quarterly payment structure"
            ]
        },
        "TENURE": {
            "description": "Loan tenure in months (NOT 'TENURE_MONTHS'). Column name is TENURE.",
            "business_rules": [
                "Column name is TENURE (not TENURE_MONTHS or TENURE_IN_MONTHS)",
                "TENURE stores the number of months as an integer",
                "Gold loans typically have tenure 6-24 months",
                "Home loans typically have tenure 60-240 months (5-20 years)",
                "Agricultural loans typically have tenure 36-120 months (3-10 years)",
                "Personal loans typically have tenure 12-60 months"
            ]
        }
    },
    "customer_non_individual_dim": {
        "REKYC_DUE_DATE": {
            "description": "ReKYC due date for non-individual customers. NOTE: This table uses REKYC_DUE_DATE (without underscore), while super_customer_dim uses RE_KYC_DUE_DATE (with underscore).",
            "business_rules": [
                "Column name is REKYC_DUE_DATE (without underscore between RE and KYC)",
                "Different from super_customer_dim.RE_KYC_DUE_DATE (which has underscore)"
            ]
        },
        "CONSTITUTION_CODE": {
            "description": "Legal constitution type of the customer",
            "valid_values": [
                {"value": "01", "meaning": "Individual"},
                {"value": "02", "meaning": "Partnership"},
                {"value": "03", "meaning": "HUF (Hindu Undivided Family)"},
                {"value": "04", "meaning": "Private Limited Company"},
                {"value": "05", "meaning": "Public Limited Company"},
                {"value": "06", "meaning": "LLP (Limited Liability Partnership)"},
                {"value": "07", "meaning": "Trust"},
                {"value": "08", "meaning": "Society"},
                {"value": "09", "meaning": "Association"},
                {"value": "10", "meaning": "Cooperative Society"},
                {"value": "11", "meaning": "Sole Proprietorship"},
                {"value": "12", "meaning": "Joint Account"},
                {"value": "13", "meaning": "Minor Account"},
                {"value": "14", "meaning": "NRI Account"},
                {"value": "15", "meaning": "Government"},
                {"value": "16", "meaning": "Public Sector Undertaking"},
                {"value": "17", "meaning": "Foreign Company"},
                {"value": "18", "meaning": "Branch Office"},
                {"value": "19", "meaning": "Liaison Office"},
                {"value": "20", "meaning": "Project Office"}
            ],
            "business_rules": [
                "Tractor Loan eligibility: Only 01 (Individual), 03 (HUF), 11 (Sole Proprietorship)",
                "Constitution codes 02-20 are for non-individual customers",
                "Constitution code 01 is for individual customers"
            ]
        },
        "IEC": {
            "description": "Import Export Code - required for businesses involved in import/export",
            "business_rules": [
                "IEC is optional for most accounts",
                "CAGBL (Current Account - Government Business Link) accounts may not have IEC codes",
                "IEC format: IEC followed by 6 digits (e.g., IEC123456)"
            ]
        }
    },
    "account_ca_dim": {
        "SCHEME_CODE": {
            "description": "Current account scheme code",
            "valid_values": [
                {"value": "CAGBL", "meaning": "Current Account - Government Business Link"},
                {"value": "CA001", "meaning": "Current Account - Standard"},
                {"value": "CA002", "meaning": "Current Account - Premium"},
                {"value": "CA003", "meaning": "Current Account - Business"},
                {"value": "CA004", "meaning": "Current Account - Zero Balance"}
            ],
            "business_rules": [
                "CAGBL accounts are for government business transactions",
                "CAGBL accounts may not have IEC codes in customer_non_individual_dim",
                "CA001, CA002, CA003, CA004 are standard current account schemes"
            ]
        }
    },
    "gold_collateral_dim": {
        "ORNAMENT_TYPE": {
            "description": "Type of gold ornament used as collateral",
            "valid_values": [
                {"value": "Mangalsutra", "meaning": "Traditional Indian gold necklace"},
                {"value": "Chain", "meaning": "Gold chain"},
                {"value": "Bangle", "meaning": "Gold bangle/bracelet"},
                {"value": "Ring", "meaning": "Gold ring"},
                {"value": "Earring", "meaning": "Gold earrings"},
                {"value": "Pendant", "meaning": "Gold pendant"},
                {"value": "Bracelet", "meaning": "Gold bracelet"},
                {"value": "Necklace", "meaning": "Gold necklace"},
                {"value": "Anklet", "meaning": "Gold anklet"},
                {"value": "Nose Pin", "meaning": "Gold nose pin"}
            ]
        },
        "PERCENTAGE": {
            "description": "Gold purity percentage",
            "business_rules": [
                "22K gold = 91.67% purity",
                "18K gold = 75% purity",
                "14K gold = 58.33% purity",
                "Mangalsutra with < 60% gold content may not meet quality standards",
                "Typical gold loans require minimum 58% purity"
            ]
        },
        "NET_WT": {
            "description": "Net weight of gold in grams (excluding stones)",
            "business_rules": [
                "Mangalsutra with < 25gms net weight may not meet minimum value requirements",
                "Loan value is typically calculated as: NET_WT * gold_rate_per_gram * loan_to_value_ratio (70-80%)"
            ]
        }
    },
    "custom_freeze_details_dim": {
        "FREZ_CODE": {
            "description": "Freeze reason code",
            "valid_values": [
                {"value": "RKYCF", "meaning": "ReKYC Freeze - account frozen due to ReKYC pending"},
                {"value": "FRAUD", "meaning": "Fraud Alert Freeze - account frozen due to fraud suspicion"},
                {"value": "COMPLIANCE", "meaning": "Compliance Freeze - account frozen for compliance reasons"},
                {"value": "KYC", "meaning": "KYC Pending Freeze - account frozen due to KYC pending"},
                {"value": "AML", "meaning": "Anti-Money Laundering Freeze"},
                {"value": "SANCTION", "meaning": "Sanction List Freeze"},
                {"value": "DORMANT", "meaning": "Dormant Account Freeze"},
                {"value": "LEGAL", "meaning": "Legal Freeze - account frozen due to legal order"},
                {"value": "OTHER", "meaning": "Other Freeze"}
            ],
            "business_rules": [
                "RKYCF freeze should be applied when RE_KYC_DUE_DATE is past due",
                "If customer has RE_KYC_DUE_DATE > 6 months ago but no RKYCF freeze, it's a compliance gap"
            ]
        }
    },
    "super_customer_dim": {
        "RE_KYC_DUE_DATE": {
            "description": "ReKYC (Re-Know Your Customer) due date. CRITICAL: Column name is RE_KYC_DUE_DATE (with underscore between RE and KYC), NOT REKYC_DUE_DATE.",
            "business_rules": [
                "Column name is RE_KYC_DUE_DATE (NOT REKYC_DUE_DATE - note the underscore)",
                "ReKYC must be done periodically (typically every 1-2 years)",
                "If RE_KYC_DUE_DATE is in the past, customer needs to complete ReKYC",
                "If RE_KYC_DUE_DATE > 6 months ago and no RKYCF freeze exists, it's a compliance gap",
                "RKYCF freeze code in custom_freeze_details_dim should match customers with overdue ReKYC",
                "For 'more than 6 months': RE_KYC_DUE_DATE < DATEADD(MONTH, -6, GETDATE())",
                "For 'less than 6 months': RE_KYC_DUE_DATE > DATEADD(MONTH, -6, GETDATE()) AND RE_KYC_DUE_DATE < GETDATE() (overdue but less than 6 months ago)"
            ]
        },
        "common_report_columns": {
            "description": "Common columns to include in customer reports for better context",
            "columns": [
                "CUST_ID", "CUST_NAME", "CLEAN_MOBILE", "PRIMARY_SOL_ID", "STATE", "CITY", 
                "RE_KYC_DUE_DATE", "STATUS", "CONSTITUTION_CODE", "PAN_NO"
            ],
            "business_rules": [
                "When generating customer reports, include CUST_NAME, CLEAN_MOBILE, PRIMARY_SOL_ID, STATE, CITY for better context",
                "These columns provide useful business information for compliance and operational reports"
            ]
        },
        "CONSTITUTION_CODE": {
            "description": "Legal constitution type (same as customer_non_individual_dim)",
            "valid_values": "See customer_non_individual_dim.CONSTITUTION_CODE"
        }
    }
}

# Table Descriptions - What each table represents
TABLE_DESCRIPTIONS = {
    "super_customer_dim": "Master customer table for ALL customers (both individual and non-individual). Contains customer master data like name, PAN, ReKYC dates, constitution code, status.",
    "customer_non_individual_dim": "Details specific to NON-INDIVIDUAL customers only. Contains CIF_ID, phone numbers, IEC codes, constitution codes. Links to super_customer_dim via CUST_ID.",
    "account_ca_dim": "CURRENT ACCOUNTS (checking accounts) for non-individual customers. Contains account numbers (ACCT_NUM), balances, scheme codes (like CAGBL). Links to customer_non_individual_dim via CUST_ID. DO NOT confuse with loan accounts.",
    "super_loan_dim": "LOAN ACCOUNT master table. Contains loan account numbers (ACCNO), product types (Gold Loan, Tractor, etc.), schemes, balances. Links to super_customer_dim via CUSTID. This is for LOAN accounts, NOT current accounts.",
    "super_loan_account_dim": "Detailed LOAN ACCOUNT information. Contains loan account numbers (ACCNO), tenure, installment types, maturity dates. Links to super_loan_dim via ACCNO. This is for LOAN accounts, NOT current accounts.",
    "caselite_loan_applications": "Gold loan APPLICATION details. Contains application IDs (APP_ID), loan account numbers (FIN_LOAN_ACCOUNT_NUMBER), schemes (LRGMI, SGL, MGL), products, status. FIN_LOAN_ACCOUNT_NUMBER links to super_loan_dim.ACCNO or super_loan_account_dim.ACCNO.",
    "gold_collateral_dim": "Gold collateral/ornament details for loan applications. Contains APP_ID (links to caselite_loan_applications.APP_ID), ornament types, gold weight, purity percentage.",
    "custom_freeze_details_dim": "Account freeze details. Contains freeze codes (RKYCF, FRAUD, etc.), freeze dates. FORACID can link to account_ca_dim.ACCT_NUM (for current accounts) or loan account numbers (for loan accounts). CUST_ID links to customer tables."
}

# Table Relationships - How to join tables correctly
TABLE_RELATIONSHIPS = {
    "caselite_loan_applications": {
        "FIN_CIF_NUMBER": "Links to customer_non_individual_dim.CIF_ID",
        "FIN_LOAN_ACCOUNT_NUMBER": "Links to super_loan_dim.ACCNO or super_loan_account_dim.ACCNO (NOT account_ca_dim.ACCT_NUM)",
        "APP_ID": "Links to gold_collateral_dim.APP_ID",
        "join_examples": [
            "caselite_loan_applications.FIN_LOAN_ACCOUNT_NUMBER = super_loan_dim.ACCNO",
            "caselite_loan_applications.FIN_LOAN_ACCOUNT_NUMBER = super_loan_account_dim.ACCNO"
        ]
    },
    "super_loan_dim": {
        "CUSTID": "Links to super_customer_dim.CUST_ID",
        "ACCNO": "Links to super_loan_account_dim.ACCNO (one-to-one relationship)",
        "join_examples": [
            "super_loan_dim.CUSTID = super_customer_dim.CUST_ID",
            "super_loan_dim.ACCNO = super_loan_account_dim.ACCNO"
        ]
    },
    "super_loan_account_dim": {
        "CUSTID": "Links to super_customer_dim.CUST_ID",
        "ACCNO": "Links to super_loan_dim.ACCNO (one-to-one relationship)",
        "join_examples": [
            "super_loan_account_dim.CUSTID = super_customer_dim.CUST_ID",
            "super_loan_account_dim.ACCNO = super_loan_dim.ACCNO"
        ]
    },
    "account_ca_dim": {
        "CUST_ID": "Links to customer_non_individual_dim.CUST_ID (NOT super_customer_dim directly)",
        "join_examples": [
            "account_ca_dim.CUST_ID = customer_non_individual_dim.CUST_ID"
        ],
        "important_note": "account_ca_dim is for CURRENT ACCOUNTS (checking accounts), NOT loan accounts. DO NOT join account_ca_dim with super_loan_dim or super_loan_account_dim using FIN_LOAN_ACCOUNT_NUMBER. FIN_LOAN_ACCOUNT_NUMBER does NOT exist in account_ca_dim or super_loan_account_dim."
    },
    "custom_freeze_details_dim": {
        "CUST_ID": "Links to super_customer_dim.CUST_ID or customer_non_individual_dim.CUST_ID",
        "FORACID": "Can link to account_ca_dim.ACCT_NUM (for current account freezes) OR loan account numbers like super_loan_dim.ACCNO (for loan account freezes)",
        "join_examples": [
            "custom_freeze_details_dim.CUST_ID = super_customer_dim.CUST_ID",
            "custom_freeze_details_dim.FORACID = account_ca_dim.ACCT_NUM",
            "custom_freeze_details_dim.FORACID = super_loan_dim.ACCNO"
        ]
    },
    "gold_collateral_dim": {
        "APP_ID": "Links to caselite_loan_applications.APP_ID",
        "join_examples": [
            "gold_collateral_dim.APP_ID = caselite_loan_applications.APP_ID"
        ]
    }
}

# Common Join Mistakes to Avoid
JOIN_WARNINGS = [
    "DO NOT join account_ca_dim (current accounts) with super_loan_dim or super_loan_account_dim (loan accounts) using FIN_LOAN_ACCOUNT_NUMBER. FIN_LOAN_ACCOUNT_NUMBER only exists in caselite_loan_applications.",
    "account_ca_dim.ACCT_NUM is for CURRENT ACCOUNTS, not loan accounts. Loan accounts use super_loan_dim.ACCNO or super_loan_account_dim.ACCNO.",
    "When joining caselite_loan_applications to loan tables, use: caselite_loan_applications.FIN_LOAN_ACCOUNT_NUMBER = super_loan_dim.ACCNO (or super_loan_account_dim.ACCNO).",
    "If question mentions 'current loan accounts', it likely means 'active loan accounts' (use super_loan_dim or super_loan_account_dim with status filters), NOT current accounts (account_ca_dim).",
    "If question mentions 'current accounts', it refers to checking accounts (account_ca_dim), NOT loan accounts."
]

# Example Queries
EXAMPLE_QUERIES = [
    {
        "question": "Show me all gold loan accounts with LRGMI scheme that are disbursed",
        "sql": "SELECT COUNT(DISTINCT FIN_LOAN_ACCOUNT_NUMBER) AS GoldLoanAccountCount FROM caselite_loan_applications WHERE PRODUCT = 'non-agricultural' AND SCHEME_NAME = 'LRGMI' AND STAGE_STATUS = 'DISBURSED'",
        "explanation": "LRGMI is Large Gold Loan Microfinance Initiative, used for non-agricultural gold loans. DISBURSED means loan has been given to customer."
    },
    {
        "question": "Find customers with ReKYC due more than 6 months ago but no RKYCF freeze",
        "sql": "SELECT c.CUST_ID, c.CUST_NAME, c.RE_KYC_DUE_DATE FROM super_customer_dim c LEFT JOIN custom_freeze_details_dim f ON c.CUST_ID = f.CUST_ID AND f.FREZ_CODE = 'RKYCF' WHERE c.RE_KYC_DUE_DATE < DATEADD(MONTH, -6, GETDATE()) AND f.FREZ_CODE IS NULL",
        "explanation": "RKYCF is ReKYC Freeze code. If RE_KYC_DUE_DATE is > 6 months ago and no RKYCF freeze exists, it's a compliance gap. Column name is RE_KYC_DUE_DATE (with underscore), NOT REKYC_DUE_DATE."
    },
    {
        "question": "Customers whose ReKYC due less than 6 months, but ReKYC Credit freeze not applied under freeze code RKYCF",
        "sql": "SELECT DISTINCT sc.CUST_ID, sc.CUST_NAME, sc.RE_KYC_DUE_DATE, sc.CLEAN_MOBILE, sc.PRIMARY_SOL_ID, sc.STATE, sc.CITY FROM super_customer_dim sc LEFT JOIN custom_freeze_details_dim cfd ON sc.CUST_ID = cfd.CUST_ID AND cfd.FREZ_CODE = 'RKYCF' AND (cfd.UNFREZ_FLG IS NULL OR cfd.UNFREZ_FLG != 'Y') WHERE sc.RE_KYC_DUE_DATE > DATEADD(MONTH, -6, GETDATE()) AND sc.RE_KYC_DUE_DATE < GETDATE() AND cfd.FREZ_CODE IS NULL AND sc.STATUS = 'ACTIVE' ORDER BY sc.RE_KYC_DUE_DATE ASC",
        "explanation": "For 'less than 6 months': Use RE_KYC_DUE_DATE > DATEADD(MONTH, -6, GETDATE()) AND RE_KYC_DUE_DATE < GETDATE() to find dates that are overdue but less than 6 months ago. Column name is RE_KYC_DUE_DATE (with underscore), NOT REKYC_DUE_DATE."
    },
    {
        "question": "Show Mangalsutra collaterals with gold content less than 60%",
        "sql": "SELECT APP_ID, ORNAMENT_TYPE, PERCENTAGE, NET_WT FROM gold_collateral_dim WHERE ORNAMENT_TYPE = 'Mangalsutra' AND PERCENTAGE < 60",
        "explanation": "Mangalsutra with < 60% gold content may not meet quality standards. PERCENTAGE column stores gold purity."
    },
    {
        "question": "Show me all current loan accounts",
        "sql": "SELECT ACCNO, CUSTID, PRODUCT_ID, SCHEME, BALANCE, ACCT_OPN_DATE FROM super_loan_dim WHERE ACCT_CLS_FLG IS NULL OR ACCT_CLS_FLG = 'N'",
        "explanation": "For loan accounts, use super_loan_dim or super_loan_account_dim. 'Current' here means active/not closed. DO NOT use account_ca_dim (that's for current/checking accounts, not loan accounts)."
    },
    {
        "question": "List all active loan accounts",
        "sql": "SELECT sla.ACCNO, sla.PRODUCT_ID, sla.SCHEME, sla.BALANCE, sla.MATURITY_DATE FROM super_loan_account_dim sla JOIN super_loan_dim sld ON sla.ACCNO = sld.ACCNO WHERE sld.ACCT_CLS_FLG IS NULL OR sld.ACCT_CLS_FLG = 'N'",
        "explanation": "Active loan accounts are in super_loan_dim or super_loan_account_dim. Join them via ACCNO. DO NOT confuse with account_ca_dim (current/checking accounts)."
    },
    {
        "question": "Tenure of less than 15 months for gold loan accounts under scheme code LRGMI for non-agricultural product variant with a monthly interest payment structure",
        "sql": "SELECT ACCNO, NAME, TENURE, SCHEME, INSTALTYPE, INT_RATE FROM super_loan_account_dim WHERE SCHEME = 'LRGMI' AND TENURE < 15 AND INSTALTYPE = 'monthly'",
        "explanation": "For tenure and installment type queries: Use super_loan_account_dim for TENURE, INSTALTYPE, and SCHEME. super_loan_account_dim has SCHEME column with scheme codes like 'LRGMI'. PREFER querying super_loan_account_dim directly instead of joining with caselite_loan_applications when you only need scheme code. Only join with caselite_loan_applications if you need columns that ONLY exist there (like PRODUCT='non-agricultural' or STAGE_STATUS)."
    },
    {
        "question": "Gold loan accounts with LRGMI scheme and monthly installment type",
        "sql": "SELECT ACCNO, NAME, TENURE, SCHEME, INSTALTYPE FROM super_loan_account_dim WHERE SCHEME = 'LRGMI' AND INSTALTYPE = 'monthly'",
        "explanation": "Use super_loan_account_dim directly for SCHEME and INSTALTYPE. No need to join with caselite_loan_applications unless you need application-specific columns."
    }
]


class KnowledgeBaseService:
    """Service to provide domain knowledge to SQLMaker agent"""
    
    def __init__(self):
        self.column_definitions = COLUMN_DEFINITIONS
        self.table_relationships = TABLE_RELATIONSHIPS
        self.table_descriptions = TABLE_DESCRIPTIONS
        self.join_warnings = JOIN_WARNINGS
        self.example_queries = EXAMPLE_QUERIES
    
    def get_column_info(self, table_name: str, column_name: str) -> Optional[Dict]:
        """Get information about a specific column"""
        if table_name in self.column_definitions:
            return self.column_definitions[table_name].get(column_name)
        return None
    
    def get_table_info(self, table_name: str) -> Optional[Dict]:
        """Get all column information for a table"""
        return self.column_definitions.get(table_name)
    
    def get_valid_values(self, table_name: str, column_name: str) -> List[str]:
        """Get valid values for a column"""
        col_info = self.get_column_info(table_name, column_name)
        if col_info and "valid_values" in col_info:
            if isinstance(col_info["valid_values"], list):
                return [v["value"] if isinstance(v, dict) else v for v in col_info["valid_values"]]
            elif isinstance(col_info["valid_values"], str):
                # Reference to another column
                return []
        return []
    
    def get_business_rules(self, table_name: str, column_name: str) -> List[str]:
        """Get business rules for a column"""
        col_info = self.get_column_info(table_name, column_name)
        if col_info and "business_rules" in col_info:
            return col_info["business_rules"]
        return []
    
    def search_knowledge(self, query: str) -> str:
        """
        Search knowledge base for relevant information
        Returns formatted string with relevant domain knowledge
        """
        query_lower = query.lower()
        results = []
        
        # Search column definitions
        for table_name, columns in self.column_definitions.items():
            for col_name, col_info in columns.items():
                if query_lower in col_name.lower() or query_lower in col_info.get("description", "").lower():
                    results.append(f"Table: {table_name}, Column: {col_name}")
                    results.append(f"  Description: {col_info.get('description', 'N/A')}")
                    if "valid_values" in col_info:
                        valid_vals = col_info["valid_values"]
                        if isinstance(valid_vals, list):
                            results.append(f"  Valid Values:")
                            for v in valid_vals[:5]:  # Limit to 5
                                if isinstance(v, dict):
                                    results.append(f"    - {v['value']}: {v.get('meaning', '')}")
                                else:
                                    results.append(f"    - {v}")
                    if "business_rules" in col_info:
                        results.append(f"  Business Rules:")
                        for rule in col_info["business_rules"][:3]:  # Limit to 3
                            results.append(f"    - {rule}")
                    results.append("")
        
        # Search example queries
        for ex in self.example_queries:
            if query_lower in ex["question"].lower() or query_lower in ex["explanation"].lower():
                results.append(f"Example Query:")
                results.append(f"  Question: {ex['question']}")
                results.append(f"  SQL: {ex['sql']}")
                results.append(f"  Explanation: {ex['explanation']}")
                results.append("")
        
        return "\n".join(results) if results else "No relevant knowledge found."
    
    def get_context_for_sql_generation(self, question: str) -> str:
        """
        Get relevant domain knowledge context for SQL generation
        Extracts key terms from question and returns relevant knowledge
        """
        question_lower = question.lower()
        context_parts = []
        
        # Extract potential table/column mentions
        tables = ["caselite_loan_applications", "super_loan_dim", "super_loan_account_dim", 
                  "customer_non_individual_dim", "account_ca_dim", "gold_collateral_dim",
                  "custom_freeze_details_dim", "super_customer_dim"]
        
        mentioned_tables = [t for t in tables if t.replace("_", " ").lower() in question_lower or t.split("_")[0] in question_lower]
        
        # Detect ambiguous terms
        is_current_accounts_question = "current account" in question_lower and "loan" not in question_lower
        is_loan_accounts_question = ("loan account" in question_lower or ("current" in question_lower and "loan" in question_lower)) or ("loan" in question_lower and "account" in question_lower)
        
        # Detect tenure/installment questions
        is_tenure_question = "tenure" in question_lower or "month" in question_lower or "installment" in question_lower or "payment structure" in question_lower or "interest payment" in question_lower
        is_scheme_question = "scheme" in question_lower or "lrgmi" in question_lower or "sgl" in question_lower or "mgl" in question_lower
        is_product_question = "product" in question_lower or "variant" in question_lower
        
        # Detect query type for report columns guidance
        is_customer_query = any(term in question_lower for term in ["customer", "cust", "kyc", "rekyc", "freeze"])
        is_loan_query = any(term in question_lower for term in ["loan", "account", "tenure", "installment"]) and not is_current_accounts_question
        is_account_query = any(term in question_lower for term in ["current account", "account balance", "scheme code"]) or is_current_accounts_question
        
        # Extract potential column mentions (schemes, products, statuses, etc.)
        key_terms = []
        if "scheme" in question_lower or "lrgmi" in question_lower or "sgl" in question_lower:
            key_terms.extend(["SCHEME_NAME", "SCHEME"])
        if "product" in question_lower or "loan" in question_lower:
            key_terms.extend(["PRODUCT", "PRODUCT_ID"])
        if "status" in question_lower or "disbursed" in question_lower or "approved" in question_lower:
            key_terms.append("STAGE_STATUS")
        if "kyc" in question_lower or "rekyc" in question_lower:
            key_terms.extend(["RE_KYC_DUE_DATE", "FREZ_CODE"])
        if "constitution" in question_lower or "tractor" in question_lower:
            key_terms.append("CONSTITUTION_CODE")
        if "mangalsutra" in question_lower or "gold" in question_lower or "collateral" in question_lower:
            key_terms.extend(["ORNAMENT_TYPE", "PERCENTAGE", "NET_WT"])
        
        # Build context
        context_parts.append("=== DOMAIN KNOWLEDGE FOR SQL GENERATION ===\n")
        
        # Add table descriptions first (critical for understanding what each table represents)
        context_parts.append("=== TABLE DESCRIPTIONS ===")
        relevant_tables = mentioned_tables if mentioned_tables else tables
        
        # Prioritize tables based on question content
        priority_tables = []
        if is_tenure_question:
            # For tenure/installment questions, prioritize super_loan_account_dim
            priority_tables = ["super_loan_account_dim", "caselite_loan_applications"]
            for table in priority_tables:
                if table in self.table_descriptions:
                    context_parts.append(f"\n{table}: {self.table_descriptions[table]}")
        
        for table_name in relevant_tables[:5]:  # Limit to 5 most relevant
            if table_name in self.table_descriptions and table_name not in priority_tables:
                context_parts.append(f"\n{table_name}: {self.table_descriptions[table_name]}")
        
        # Add critical column mappings for tenure/installment questions
        if is_tenure_question:
            context_parts.append("\n=== CRITICAL FOR TENURE/INSTALLMENT QUESTIONS ===")
            context_parts.append("super_loan_account_dim has:")
            context_parts.append("  - TENURE (loan tenure in months)")
            context_parts.append("  - INSTALTYPE (installment type: 'monthly', 'quarterly', 'yearly')")
            context_parts.append("  - SCHEME (scheme code like 'LRGMI', 'SGL', 'MGL') - PREFER using this directly!")
            context_parts.append("  - PRODUCT_ID (product type like 'Gold Loan', 'Tractor')")
            context_parts.append("  - ACCNO (loan account number)")
            context_parts.append("\ncaselite_loan_applications has:")
            context_parts.append("  - SCHEME_NAME (scheme code like 'LRGMI', 'SGL', 'MGL') - same as super_loan_account_dim.SCHEME")
            context_parts.append("  - PRODUCT (product variant like 'non-agricultural', 'agricultural')")
            context_parts.append("  - STAGE_STATUS (application status like 'DISBURSED', 'PENDING')")
            context_parts.append("  - FIN_LOAN_ACCOUNT_NUMBER (joins with super_loan_account_dim.ACCNO)")
            context_parts.append("\nIMPORTANT RULES:")
            context_parts.append("  1. PREFER querying super_loan_account_dim directly for SCHEME, TENURE, INSTALTYPE")
            context_parts.append("  2. Only join with caselite_loan_applications if you need:")
            context_parts.append("     - PRODUCT='non-agricultural' or 'agricultural' (not PRODUCT_ID)")
            context_parts.append("     - STAGE_STATUS (application status)")
            context_parts.append("     - Application dates (APPLIED_DATE_LED, APPROVED_ON)")
            context_parts.append("  3. If query only mentions scheme code (like 'LRGMI'), use super_loan_account_dim.SCHEME directly")
            context_parts.append("  4. If query mentions 'product variant' or 'non-agricultural', then join with caselite_loan_applications")
        
        # Add join warnings if relevant
        if is_current_accounts_question or is_loan_accounts_question or "account" in question_lower:
            context_parts.append("\n=== IMPORTANT JOIN WARNINGS ===")
            for warning in self.join_warnings[:3]:  # Limit to 3 most relevant
                context_parts.append(f"- {warning}")
        
        # Add table relationships for mentioned tables
        if mentioned_tables:
            context_parts.append("\n=== TABLE RELATIONSHIPS ===")
            for table_name in mentioned_tables[:3]:  # Limit to 3
                if table_name in self.table_relationships:
                    rel_info = self.table_relationships[table_name]
                    context_parts.append(f"\n{table_name} relationships:")
                    for key, value in rel_info.items():
                        if key != "join_examples":
                            context_parts.append(f"  - {key}: {value}")
                    if "join_examples" in rel_info:
                        context_parts.append(f"  Join examples:")
                        for example in rel_info["join_examples"][:2]:
                            context_parts.append(f"    - {example}")
        
        # Add relevant column definitions
        context_parts.append("\n=== COLUMN DEFINITIONS ===")
        for table_name in (mentioned_tables or tables[:3]):  # Limit to first 3 if none mentioned
            if table_name in self.column_definitions:
                context_parts.append(f"\nTable: {table_name}")
                for col_name, col_info in self.column_definitions[table_name].items():
                    if col_name == "common_report_columns":
                        # Add common report columns guidance
                        if is_customer_query and table_name == "super_customer_dim":
                            context_parts.append(f"  Common Report Columns: {', '.join(col_info.get('columns', []))}")
                            context_parts.append(f"    Include these columns in customer reports for better context")
                        continue
                    if not key_terms or col_name in key_terms:
                        context_parts.append(f"  Column: {col_name}")
                        context_parts.append(f"    Description: {col_info.get('description', 'N/A')}")
                        if "valid_values" in col_info and isinstance(col_info["valid_values"], list):
                            context_parts.append(f"    Valid Values:")
                            for v in col_info["valid_values"][:3]:  # Limit to 3
                                if isinstance(v, dict):
                                    context_parts.append(f"      - {v['value']}: {v.get('meaning', '')}")
                        if "business_rules" in col_info:
                            context_parts.append(f"    Business Rules:")
                            for rule in col_info["business_rules"][:2]:  # Limit to 2
                                context_parts.append(f"      - {rule}")
        
        # Add common report columns guidance
        if is_customer_query:
            context_parts.append("\n=== REPORT COLUMNS GUIDANCE ===")
            context_parts.append("For customer reports, include these useful columns:")
            context_parts.append("  - CUST_ID, CUST_NAME, CLEAN_MOBILE, PRIMARY_SOL_ID, STATE, CITY")
            context_parts.append("  - Plus any specific columns mentioned in the question (e.g., RE_KYC_DUE_DATE)")
        elif is_loan_query:
            context_parts.append("\n=== REPORT COLUMNS GUIDANCE ===")
            context_parts.append("For loan reports, include these useful columns:")
            context_parts.append("  - ACCNO, NAME, PRODUCT_ID, SCHEME, BALANCE, ACCT_OPN_DATE")
            context_parts.append("  - Plus any specific columns mentioned in the question (e.g., TENURE, INSTALTYPE)")
        elif is_account_query:
            context_parts.append("\n=== REPORT COLUMNS GUIDANCE ===")
            context_parts.append("For account reports, include these useful columns:")
            context_parts.append("  - ACCT_NUM, ACCT_NAME, SCHEME_CODE, BALANCE, SANCT_LIM")
            context_parts.append("  - Plus any specific columns mentioned in the question")
        
        # Add relevant example queries
        context_parts.append("\n=== EXAMPLE QUERIES ===")
        for ex in self.example_queries[:2]:  # Limit to 2 examples
            if any(term in question_lower for term in ex["question"].lower().split()[:3]):
                context_parts.append(f"\nQuestion: {ex['question']}")
                context_parts.append(f"SQL: {ex['sql']}")
                context_parts.append(f"Explanation: {ex['explanation']}")
        
        return "\n".join(context_parts)


# Singleton instance
_knowledge_base = None

def get_knowledge_base() -> KnowledgeBaseService:
    """Get singleton knowledge base instance"""
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = KnowledgeBaseService()
    return _knowledge_base

