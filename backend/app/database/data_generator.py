"""
Enhanced Synthetic Data Generator for 8 BIU Star Schema Tables
Creates realistic banking domain data with meaningful codes, schemes, products, and relationships.
Includes date range distribution (some recent, some 3 months old) to simulate real-world data freshness.
"""
import random
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from app.database.schema import (
    SuperCustomerDim, CustomerNonIndividualDim, AccountCaDim,
    SuperLoanDim, SuperLoanAccountDim, CaseliteLoanApplications,
    GoldCollateralDim, CustomFreezeDetailsDim
)

# Banking Domain Knowledge - Valid Values
SCHEME_NAMES = [
    "LRGMI",  # Large Gold Loan Microfinance Initiative
    "SGL",    # Small Gold Loan
    "MGL",    # Medium Gold Loan
    "AGRI",   # Agricultural Loan Scheme
    "MSME",   # Micro, Small & Medium Enterprise
    "PRI",    # Priority Sector Loan
    "RETAIL", # Retail Loan Scheme
    "HOUSING",# Housing Loan Scheme
    "EDU",    # Education Loan Scheme
    "VEHICLE" # Vehicle Loan Scheme
]

PRODUCT_TYPES = [
    "Gold Loan",
    "Personal Loan",
    "Home Loan",
    "Car Loan",
    "Tractor Loan",
    "Agricultural Loan",
    "Business Loan",
    "Education Loan",
    "Two-Wheeler Loan"
]

PRODUCT_CATEGORIES = {
    "non-agricultural": ["Gold Loan", "Personal Loan", "Home Loan", "Car Loan", "Business Loan", "Education Loan", "Two-Wheeler Loan"],
    "agricultural": ["Tractor Loan", "Agricultural Loan"],
    "commercial": ["Business Loan", "MSME Loan"]
}

CONSTITUTION_CODES = {
    "01": "Individual",
    "02": "Partnership",
    "03": "HUF (Hindu Undivided Family)",
    "04": "Private Limited Company",
    "05": "Public Limited Company",
    "06": "LLP (Limited Liability Partnership)",
    "07": "Trust",
    "08": "Society",
    "09": "Association",
    "10": "Cooperative Society",
    "11": "Sole Proprietorship",
    "12": "Joint Account",
    "13": "Minor Account",
    "14": "NRI Account",
    "15": "Government",
    "16": "Public Sector Undertaking",
    "17": "Foreign Company",
    "18": "Branch Office",
    "19": "Liaison Office",
    "20": "Project Office"
}

TRACTOR_ELIGIBLE_CONSTITUTIONS = ["01", "03", "11"]  # Individual, HUF, Sole Proprietorship

FREEZE_CODES = {
    "RKYCF": "ReKYC Freeze",
    "FRAUD": "Fraud Alert Freeze",
    "COMPLIANCE": "Compliance Freeze",
    "KYC": "KYC Pending Freeze",
    "AML": "Anti-Money Laundering Freeze",
    "SANCTION": "Sanction List Freeze",
    "DORMANT": "Dormant Account Freeze",
    "LEGAL": "Legal Freeze",
    "OTHER": "Other Freeze"
}

SCHEME_CODES_CA = {
    "CAGBL": "Current Account - Government Business Link",
    "CA001": "Current Account - Standard",
    "CA002": "Current Account - Premium",
    "CA003": "Current Account - Business",
    "CA004": "Current Account - Zero Balance"
}

ORNAMENT_TYPES = [
    "Mangalsutra",
    "Chain",
    "Bangle",
    "Ring",
    "Earring",
    "Pendant",
    "Bracelet",
    "Necklace",
    "Anklet",
    "Nose Pin"
]

STATES = ["Maharashtra", "Karnataka", "Tamil Nadu", "Delhi", "Gujarat", "Rajasthan", "Punjab", "West Bengal", "Andhra Pradesh", "Telangana"]
CITIES = {
    "Maharashtra": ["Mumbai", "Pune", "Nagpur", "Nashik", "Aurangabad"],
    "Karnataka": ["Bangalore", "Mysore", "Hubli", "Mangalore"],
    "Tamil Nadu": ["Chennai", "Coimbatore", "Madurai", "Salem"],
    "Delhi": ["New Delhi", "Gurgaon", "Noida"],
    "Gujarat": ["Ahmedabad", "Surat", "Vadodara", "Rajkot"],
    "Rajasthan": ["Jaipur", "Jodhpur", "Udaipur"],
    "Punjab": ["Chandigarh", "Ludhiana", "Amritsar"],
    "West Bengal": ["Kolkata", "Howrah"],
    "Andhra Pradesh": ["Hyderabad", "Vijayawada", "Visakhapatnam"],
    "Telangana": ["Hyderabad", "Warangal"]
}

STAGE_STATUSES = ["APPROVED", "PENDING", "DISBURSED", "REJECTED", "CANCELLED", "ON_HOLD"]
ACCT_STATUSES = ["ACTIVE", "CLOSED", "DORMANT", "FROZEN", "SUSPENDED"]


def _gen_audit_timestamps(stale_probability=0.3) -> tuple:
    """
    Generate (inserted_on, last_updated_ts) with date range distribution.
    
    Args:
        stale_probability: Probability that data is 3+ months old (default 30%)
    
    Returns:
        (inserted_on, last_updated_ts) tuple
    """
    now = datetime.now()
    
    # 30% chance of stale data (3+ months old)
    if random.random() < stale_probability:
        # Stale data: inserted 90-120 days ago, updated 85-90 days ago
        days_ago = random.randint(90, 120)
        inserted_on = now - timedelta(days=days_ago, hours=random.randint(0, 23), minutes=random.randint(0, 59))
        last_updated = inserted_on + timedelta(days=random.randint(0, 5), hours=random.randint(0, 23), minutes=random.randint(0, 59))
    else:
        # Recent data: inserted 1-30 days ago, updated within last 7 days
        days_ago = random.randint(1, 30)
        inserted_on = now - timedelta(days=days_ago, hours=random.randint(0, 23), minutes=random.randint(0, 59))
        last_updated = inserted_on + timedelta(days=random.randint(0, min(7, days_ago)), hours=random.randint(0, 23), minutes=random.randint(0, 59))
    
    if last_updated > now:
        last_updated = now
    
    return inserted_on, last_updated


def generate_customer_ids(count=100):
    """Generate unique customer IDs"""
    return [f"CUST{str(i).zfill(6)}" for i in range(1, count + 1)]


def generate_cif_ids(count=100):
    """Generate unique CIF IDs"""
    return [f"CIF{str(i).zfill(8)}" for i in range(1, count + 1)]


def generate_account_numbers(prefix="CA", count=150):
    """Generate account numbers"""
    return [f"{prefix}{str(i).zfill(10)}" for i in range(1, count + 1)]


def generate_loan_accounts(prefix="LN", count=200):
    """Generate loan account numbers"""
    return [f"{prefix}{str(i).zfill(10)}" for i in range(1, count + 1)]


def generate_app_ids(count=150):
    """Generate application IDs"""
    return [f"APP{str(i).zfill(8)}" for i in range(1, count + 1)]


def generate_mobile_numbers(count=50):
    """Generate mobile numbers (some will be reused for Question 2)"""
    base_numbers = [f"9{random.randint(100000000, 999999999)}" for _ in range(count)]
    # Add some duplicates for Question 2 scenario
    duplicated = base_numbers[:10] * 12  # 10 numbers used 12 times each
    return base_numbers + duplicated


def populate_super_customer_dim(db: Session, customer_ids):
    """Populate SUPER_CUSTOMER_DIM with realistic customer data including Question 1 scenarios"""
    customers = []
    
    # Question 1: Some customers with ReKYC due > 6 months but no RKYCF freeze
    today_dt = datetime.now()
    today = today_dt.date()
    six_months_ago = today - timedelta(days=180)
    
    for i, cust_id in enumerate(customer_ids):
        inserted_on, last_updated_ts = _gen_audit_timestamps(stale_probability=0.3)  # 30% stale data
        
        # 20% will have ReKYC due > 6 months (for Question 1)
        if i < 20:
            re_kyc_due = six_months_ago - timedelta(days=random.randint(1, 90))
        else:
            re_kyc_due = today + timedelta(days=random.randint(30, 365))
        
        # Select state and corresponding city
        state = random.choice(STATES)
        city = random.choice(CITIES.get(state, ["Unknown"]))
        
        # Constitution code and description
        const_code = random.choice(list(CONSTITUTION_CODES.keys()))
        const_desc = CONSTITUTION_CODES[const_code]
        
        # Customer status
        if random.random() < 0.85:
            status = "ACTIVE"
            suspended = False
            blacklisted = False
        elif random.random() < 0.95:
            status = "SUSPENDED"
            suspended = True
            blacklisted = False
        else:
            status = "BLACKLISTED"
            suspended = False
            blacklisted = True

        customer = SuperCustomerDim(
            CUST_ID=cust_id,
            UCIC=f"UCIC{str(i+1).zfill(10)}",
            CUST_NAME=f"Customer {i+1}",
            CLEAN_FULL_NAME=f"Customer {i+1}",
            CLEAN_FIRST_NAME=f"Customer",
            CLEAN_LAST_NAME=f"{i+1}",
            CLEAN_MOBILE=generate_mobile_numbers(1)[0],
            PAN_NO=f"ABCDE{random.randint(1000, 9999)}F",
            CUST_DOB=datetime(1970, 1, 1).date() + timedelta(days=random.randint(0, 15000)),
            GENDER=random.choice(["M", "F", "O"]),
            RE_KYC_DUE_DATE=re_kyc_due,
            KYC_DATE=re_kyc_due - timedelta(days=random.randint(365, 730)),
            RETAIL_LAST_KYC_DATE=re_kyc_due - timedelta(days=random.randint(365, 730)),
            PRIMARY_SOL_ID=f"SOL{random.randint(1, 100):03d}",
            STATE=state,
            CITY=city,
            CONSTITUTION_CODE=const_code,
            CONSTITUTION_DESC_FINACLE=const_desc,
            STATUS=status,
            SUSPENDED=suspended,
            BLACKLISTED=blacklisted,
            CURRENT_DT=today,
            INSERTED_ON=inserted_on,
            LAST_UPDATED_TS=last_updated_ts
        )
        customers.append(customer)
    
    db.add_all(customers)
    db.commit()
    return customers


def populate_customer_non_individual_dim(db: Session, customer_ids, cif_ids):
    """Populate CUSTOMER_NON_INDIVIDUAL_DIM with realistic non-individual customer data including Questions 2, 4, 7 scenarios"""
    customers = []
    mobile_numbers = generate_mobile_numbers(120)
    
    # Question 2: Some mobile numbers used in > 10 CIFs
    # Question 4: Some accounts missing IEC code
    # Question 7: Some customers with wrong constitution code for Tractor loans
    
    for i, (cust_id, cif_id) in enumerate(zip(customer_ids, cif_ids)):
        inserted_on, last_updated_ts = _gen_audit_timestamps(stale_probability=0.25)  # 25% stale data
        
        # For Question 2: Reuse mobile numbers for first 120 customers
        # Ensure they have partnership+ constitution codes (02-20) and active accounts
        if i < 120:
            phone = mobile_numbers[i % 12]  # 12 customers per mobile (for > 10 scenario)
            # For Question 2: Use partnership+ constitution codes (02-20)
            constitution = random.choice(["02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20"])
        else:
            phone = f"9{random.randint(100000000, 999999999)}"
            # Can be any constitution code
            constitution = random.choice(list(CONSTITUTION_CODES.keys()))
        
        # Question 4: Some accounts missing IEC (CAGBL accounts - Government Business Link)
        if i < 15:  # 15 accounts will be CAGBL without IEC
            iec = None
        else:
            # IEC (Import Export Code) - only for businesses that import/export
            iec = f"IEC{random.randint(100000, 999999)}" if random.random() > 0.3 else None
        
        # Question 7: Some customers with wrong constitution for Tractor (only for customers not in Question 2 group)
        # Eligible: 01, 03, 11 (Individual, HUF, Sole Proprietorship)
        if i >= 120 and i < 130:  # 10 customers with wrong constitution (outside Question 2 group)
            constitution = random.choice(["02", "04", "05", "06", "07", "08", "09", "10"])
        
        const_desc = CONSTITUTION_CODES.get(constitution, "Unknown")
        
        # Select state and city
        state = random.choice(STATES)
        city = random.choice(CITIES.get(state, ["Unknown"]))
        
        # Customer status
        if random.random() < 0.90:
            status = "ACTIVE"
        else:
            status = random.choice(["SUSPENDED", "CLOSED", "DORMANT"])
        
        customer = CustomerNonIndividualDim(
            CUST_ID=cust_id,
            CIF_ID=cif_id,
            CUST_NAME=f"Non-Individual Customer {i+1}",
            FIRST_NAME=f"Customer",
            LAST_NAME=f"{i+1}",
            MIDDLE_NAME="",
            PHONE_NUMBER=phone,
            EMAIL_ID=f"customer{i+1}@example.com",
            PAN=f"ABCDE{random.randint(1000, 9999)}F",
            IEC=iec,
            CONSTITUTION_CODE=constitution,
            CONSTITUTION_DESC=const_desc,
            OPENING_DATE=datetime.now().date() - timedelta(days=random.randint(100, 2000)),
            PRIMARY_SOL_ID=f"SOL{random.randint(1, 100):03d}",
            STATE=state,
            CITY=city,
            REKYC_DUE_DATE=datetime.now().date() + timedelta(days=random.randint(30, 365)),
            LATEST_KYC_DATE=datetime.now().date() - timedelta(days=random.randint(30, 365)),
            STATUS=status,
            INSERTED_ON=inserted_on,
            LAST_UPDATED_TS=last_updated_ts,
        )
        customers.append(customer)
    
    db.add_all(customers)
    db.commit()
    return customers


def populate_account_ca_dim(db: Session, customer_ids, cif_ids):
    """Populate ACCOUNT_CA_DIM with realistic current account data including Question 4 scenarios"""
    accounts = []
    account_nums = generate_account_numbers("CA", 150)
    
    for i, (cust_id, cif_id) in enumerate(zip(customer_ids[:150], cif_ids[:150])):
        inserted_on, last_updated_ts = _gen_audit_timestamps(stale_probability=0.2)  # 20% stale data
        
        # Question 4: Some CAGBL accounts without IEC (Government Business Link accounts)
        if i < 15:
            scheme_code = "CAGBL"
            scheme_desc = SCHEME_CODES_CA["CAGBL"]
            # CAGBL accounts typically have higher balances
            balance = Decimal(str(round(random.uniform(500000, 5000000), 2)))
            sanct_lim = Decimal(str(round(random.uniform(1000000, 10000000), 2)))
        else:
            scheme_code = random.choice(list(SCHEME_CODES_CA.keys()))
            scheme_desc = SCHEME_CODES_CA[scheme_code]
            balance = Decimal(str(round(random.uniform(10000, 1000000), 2)))
            sanct_lim = Decimal(str(round(random.uniform(50000, 5000000), 2)))
        
        # Account status distribution
        if random.random() < 0.85:
            acct_status = "ACTIVE"
        elif random.random() < 0.95:
            acct_status = "DORMANT"
        else:
            acct_status = random.choice(["FROZEN", "SUSPENDED"])
        
        # Freeze logic
        debit_frez_flag = False
        debit_frez_date = None
        debit_frez_reason = None
        if acct_status == "FROZEN" or random.random() < 0.15:
            debit_frez_flag = True
            debit_frez_date = datetime.now().date() - timedelta(days=random.randint(1, 90))
            debit_frez_reason = random.choice(["KYC", "FRAUD", "COMPLIANCE", "AML", "LEGAL"])
        
        account = AccountCaDim(
            ACCT_NUM=account_nums[i],
            CUST_ID=cust_id,
            ACCT_NAME=f"Current Account {i+1}",
            SCHEME_CODE=scheme_code,
            SCHEME_DESC=scheme_desc,
            ACCT_OPN_DATE=datetime.now().date() - timedelta(days=random.randint(100, 2000)),
            ACCT_STATUS=acct_status,
            DEBIT_FREZ_FLAG=debit_frez_flag,
            DEBIT_FREZ_DATE=debit_frez_date,
            DEBIT_FREZ_REASON_CODE=debit_frez_reason,
            SOL_ID=f"SOL{random.randint(1, 100):03d}",
            BALANCE=balance,
            SANCT_LIM=sanct_lim,
            CURRENT_DT=datetime.now().date(),
            INSERTED_ON=inserted_on,
            LAST_UPDATED_TS=last_updated_ts,
        )
        accounts.append(account)
    
    db.add_all(accounts)
    db.commit()
    return accounts


def populate_super_loan_dim(db: Session, customer_ids):
    """Populate SUPER_LOAN_DIM with realistic loan data including Question 7 scenarios"""
    loans = []
    loan_accounts = generate_loan_accounts("LN", 200)
    
    for i, cust_id in enumerate(customer_ids[:200]):
        inserted_on, last_updated_ts = _gen_audit_timestamps(stale_probability=0.25)  # 25% stale data
        
        # Question 7: Some Tractor loans with wrong constitution
        if i < 20:
            product_id = "Tractor Loan"
            scheme = random.choice(["AGRI", "PRI", "Tractor Scheme"])
            int_rate = Decimal(str(round(random.uniform(7.0, 10.0), 4)))  # Lower for agri
            balance = Decimal(str(round(random.uniform(500000, 5000000), 2)))  # Tractor loans typically higher
            sanct_lim = Decimal(str(round(random.uniform(800000, 8000000), 2)))
        else:
            product_id = random.choice(PRODUCT_TYPES)
            # Match scheme to product
            if product_id == "Gold Loan":
                scheme = random.choice(["LRGMI", "SGL", "MGL"])
            elif product_id in ["Tractor Loan", "Agricultural Loan"]:
                scheme = random.choice(["AGRI", "PRI"])
            elif product_id == "Home Loan":
                scheme = "HOUSING"
            elif product_id == "Education Loan":
                scheme = "EDU"
            elif product_id == "Car Loan" or product_id == "Two-Wheeler Loan":
                scheme = "VEHICLE"
            else:
                scheme = random.choice(["RETAIL", "MSME", "PRI"])
            
            int_rate = Decimal(str(round(random.uniform(8.5, 15.5), 4)))
            balance = Decimal(str(round(random.uniform(100000, 5000000), 2)))
            sanct_lim = Decimal(str(round(random.uniform(200000, 10000000), 2)))
        
        # Account status
        if random.random() < 0.75:
            acct_cls_flg = "N"
            acct_cls_date = None
            acct_label = random.choice(["Active", "Regular"])
        elif random.random() < 0.90:
            acct_cls_flg = "N"
            acct_cls_date = None
            acct_label = "NPA"  # Non-Performing Asset
        else:
            acct_cls_flg = "Y"
            acct_cls_date = datetime.now().date() - timedelta(days=random.randint(1, 365))
            acct_label = "Closed"
        
        # Freeze code (if account is frozen)
        frez_code = None
        if acct_label == "NPA" or random.random() < 0.05:
            frez_code = random.choice(["LEGAL", "COMPLIANCE", "OTHER"])
        
        state = random.choice(STATES)
        
        loan = SuperLoanDim(
            ACCNO=loan_accounts[i],
            CUSTID=cust_id,
            NAME=f"Loan Customer {i+1}",
            PRODUCT_ID=product_id,
            DESCRIPTION=f"{product_id} - {scheme} Scheme",
            SCHEME=scheme,
            STYPE=random.choice(["A", "B", "C", "D"]),
            BALANCE=balance,
            SANCT_LIM=sanct_lim,
            INT_RATE=int_rate,
            FREZ_CODE=frez_code,
            ACCT_OPN_DATE=datetime.now().date() - timedelta(days=random.randint(100, 2000)),
            ACCT_CLS_DATE=acct_cls_date,
            ACCT_CLS_FLG=acct_cls_flg,
            SOL_ID=f"SOL{random.randint(1, 100):03d}",
            STATE=state,
            CURRENCY="INR",
            TYPE_ADVANCE_CODE=f"TAC{random.randint(1, 20):02d}",
            ACCT_LABEL=acct_label,
            INSERTED_ON=inserted_on,
            LAST_UPDATED_TS=last_updated_ts,
        )
        loans.append(loan)
    
    db.add_all(loans)
    db.commit()
    return loans


def populate_super_loan_account_dim(db: Session, loan_accounts):
    """Populate SUPER_LOAN_ACCOUNT_DIM with realistic loan account details"""
    loan_accounts_data = []
    
    for i, accno in enumerate(loan_accounts):
        inserted_on, last_updated_ts = _gen_audit_timestamps(stale_probability=0.2)  # 20% stale data
        
        # Question 3: Some loans with tenure > 12 months, scheme LRGMI, non-agricultural, monthly
        if i < 25:
            scheme = "LRGMI"  # Large Gold Loan Microfinance Initiative
            product_id = "Gold Loan"
            tenure = random.randint(13, 24)  # > 12 months
            inst_type = "monthly"
            int_rate = Decimal(str(round(random.uniform(9.0, 12.5), 4)))
        elif i < 50:
            # Other gold loan schemes
            scheme = random.choice(["SGL", "MGL"])
            product_id = "Gold Loan"
            tenure = random.randint(6, 18)
            inst_type = random.choice(["monthly", "quarterly"])
            int_rate = Decimal(str(round(random.uniform(9.5, 13.0), 4)))
        elif i < 75:
            # Home loans (typically longer tenure, quarterly/yearly)
            scheme = "HOUSING"
            product_id = "Home Loan"
            tenure = random.randint(60, 240)  # 5-20 years
            inst_type = random.choice(["monthly", "quarterly"])
            int_rate = Decimal(str(round(random.uniform(7.5, 10.5), 4)))
        elif i < 100:
            # Agricultural loans
            scheme = random.choice(["AGRI", "PRI"])
            product_id = random.choice(["Tractor Loan", "Agricultural Loan"])
            tenure = random.randint(36, 120)  # 3-10 years
            inst_type = random.choice(["monthly", "quarterly", "yearly"])
            int_rate = Decimal(str(round(random.uniform(7.0, 10.0), 4)))
        else:
            # General mix
            scheme = random.choice(SCHEME_NAMES)
            product_id = random.choice(PRODUCT_TYPES)
            tenure = random.randint(6, 84)  # 6 months to 7 years
            inst_type = random.choice(["monthly", "quarterly", "yearly"])
            int_rate = Decimal(str(round(random.uniform(8.5, 15.5), 4)))
        
        # Calculate EMI based on loan amount and tenure
        loan_amount = Decimal(str(round(random.uniform(100000, 5000000), 2)))
        # Simplified EMI calculation: (P * R * (1+R)^N) / ((1+R)^N - 1)
        monthly_rate = int_rate / Decimal("1200")  # Convert annual to monthly
        if monthly_rate > 0:
            emi = loan_amount * monthly_rate * ((1 + monthly_rate) ** tenure) / (((1 + monthly_rate) ** tenure) - 1)
            emi = Decimal(str(round(emi, 2)))
        else:
            emi = loan_amount / Decimal(str(tenure))
        
        balance = loan_amount * Decimal(str(round(random.uniform(0.3, 0.95), 2)))  # 30-95% of loan amount remaining
        sanct_lim = loan_amount * Decimal("1.1")  # 10% buffer
        
        # Calculate dates - mix of recent (30%) and older (70%) dates for realistic testing
        if random.random() < 0.3:
            # 30% recent accounts (within last 3 months)
            acct_opn_date = datetime.now().date() - timedelta(days=random.randint(1, 90))
        else:
            # 70% older accounts (100-1000 days old)
            acct_opn_date = datetime.now().date() - timedelta(days=random.randint(100, 1000))
        emi_start_dt = acct_opn_date + timedelta(days=random.randint(1, 30))
        maturity_date = emi_start_dt + timedelta(days=tenure * 30)  # Approximate
        next_installment = datetime.now().date() + timedelta(days=random.randint(1, 30))
        
        state = random.choice(STATES)
        
        loan_acc = SuperLoanAccountDim(
            ACCNO=accno,
            CUSTID=f"CUST{str(i+1).zfill(6)}",
            NAME=f"Loan Account {i+1}",
            SCHEME=scheme,
            PRODUCT_ID=product_id,
            INSTALTYPE=inst_type,
            INSTLMODE=random.choice(["Auto", "Manual"]),
            EMI=emi,
            TENURE=tenure,
            EMI_START_DT=emi_start_dt,
            NEXT_INSTALLMENT_DATE=next_installment,
            INT_RATE=int_rate,
            BALANCE=balance,
            SANCT_LIM=sanct_lim,
            FREZ_CODE=None,
            ACCT_OPN_DATE=acct_opn_date,
            MATURITY_DATE=maturity_date,
            SOL_ID=f"SOL{random.randint(1, 100):03d}",
            STATE=state,
            INSERTED_ON=inserted_on,
            LAST_UPDATED_TS=last_updated_ts,
        )
        loan_accounts_data.append(loan_acc)
    
    db.add_all(loan_accounts_data)
    db.commit()
    return loan_accounts_data


def populate_caselite_loan_applications(db: Session, app_ids):
    """Populate CASELITE_LOAN_APPLICATIONS with realistic banking data including Question 3 scenarios"""
    applications = []
    loan_accounts = generate_loan_accounts("GL", 150)
    
    for i, app_id in enumerate(app_ids):
        inserted_on, last_updated_ts = _gen_audit_timestamps(stale_probability=0.25)  # 25% stale data
        
        # Question 3: Some applications with LRGMI, non-agricultural, tenure > 12, monthly
        if i < 30:
            scheme_name = "LRGMI"  # Large Gold Loan Microfinance Initiative
            product = "non-agricultural"
            tenure = random.randint(13, 24)  # > 12 months
            stage_status = random.choice(["DISBURSED", "APPROVED"])  # More likely to be disbursed for LRGMI
        elif i < 60:
            # Mix of other schemes with realistic products
            scheme_name = random.choice(["SGL", "MGL", "RETAIL"])
            product = random.choice(["non-agricultural", "commercial"])
            tenure = random.randint(6, 36)
            stage_status = random.choice(STAGE_STATUSES)
        elif i < 90:
            # Agricultural loans
            scheme_name = random.choice(["AGRI", "PRI"])
            product = "agricultural"
            tenure = random.randint(12, 60)  # Agricultural loans typically longer tenure
            stage_status = random.choice(["APPROVED", "DISBURSED", "PENDING"])
        else:
            # General mix
            scheme_name = random.choice(SCHEME_NAMES)
            product = random.choice(list(PRODUCT_CATEGORIES.keys()))
            tenure = random.randint(6, 48)
            stage_status = random.choice(STAGE_STATUSES)
        
        # Realistic lending rates based on product type
        if product == "agricultural":
            lending_rate = Decimal(str(round(random.uniform(7.0, 10.0), 4)))  # Lower for agri
        elif scheme_name in ["LRGMI", "SGL", "MGL"]:
            lending_rate = Decimal(str(round(random.uniform(9.0, 12.5), 4)))  # Gold loans
        else:
            lending_rate = Decimal(str(round(random.uniform(8.5, 15.5), 4)))
        
        # Loan amounts based on scheme
        if scheme_name in ["LRGMI", "SGL", "MGL"]:
            agreed_amt = Decimal(str(round(random.uniform(50000, 2000000), 2)))  # Gold loans: 50K-20L
        elif product == "agricultural":
            agreed_amt = Decimal(str(round(random.uniform(200000, 5000000), 2)))  # Agri: 2L-50L
        else:
            agreed_amt = Decimal(str(round(random.uniform(100000, 3000000), 2)))
        
        net_disb_amt = agreed_amt * Decimal("0.95")  # Typically 95% of agreed amount
        
        application = CaseliteLoanApplications(
            APP_ID=app_id,
            CAS_LITE_ID=f"CL{str(i+1).zfill(8)}",
            FIN_CIF_NUMBER=f"CIF{str(i+1).zfill(8)}",
            FIN_LOAN_ACCOUNT_NUMBER=loan_accounts[i],
            SCHEME_NAME=scheme_name,
            PRODUCT=product,
            TENURE=tenure,
            LENDING_RATE=lending_rate,
            AGREED_LN_AMT=agreed_amt,
            NET_DISB_AMT=net_disb_amt,
            APPLIED_DATE_LED=datetime.now().date() - timedelta(days=random.randint(1, 365)),
            APPROVED_ON=datetime.now().date() - timedelta(days=random.randint(1, 30)) if stage_status in ["APPROVED", "DISBURSED"] else None,
            STAGE_STATUS=stage_status,
            SOL_ID=f"SOL{random.randint(1, 100):03d}",
            FIRST_NAME=f"Applicant",
            LAST_NAME=f"{i+1}",
            MOBILE_NO=f"9{random.randint(100000000, 999999999)}",
            PAN_NO=f"ABCDE{random.randint(1000, 9999)}F",
            CIBIL_SCORE=random.randint(600, 850),
            ACTIVE_IND="Y",
            INSERTED_ON=inserted_on,
            LAST_UPDATED_TS=last_updated_ts,
        )
        applications.append(application)
    
    db.add_all(applications)
    db.commit()
    return applications


def populate_gold_collateral_dim(db: Session, app_ids):
    """Populate GOLD_COLLATERAL_DIM with realistic gold collateral data including Questions 5 & 6 scenarios"""
    collaterals = []
    account_nums = generate_account_numbers("GL", 150)
    
    for i, app_id in enumerate(app_ids):
        inserted_on, last_updated_ts = _gen_audit_timestamps(stale_probability=0.2)  # 20% stale data
        
        # Question 5: Some Mangalsutra with gold content < 60%
        # Question 6: Some Mangalsutra with net weight < 25gms
        
        if i < 20:
            ornament_type = "Mangalsutra"
            # Question 5 scenario: gold content < 60% (typically 22K gold = 91.67%, but some may be lower purity)
            percentage = Decimal(str(round(random.uniform(40, 59), 2)))  # Below 60%
            gross_wt = Decimal(str(round(random.uniform(20, 50), 3)))
            net_wt = Decimal(str(round(random.uniform(15, 24), 3)))  # Question 6: < 25gms
        elif i < 40:
            ornament_type = "Mangalsutra"
            percentage = Decimal(str(round(random.uniform(60, 95), 2)))  # Above 60% (22K/24K gold)
            gross_wt = Decimal(str(round(random.uniform(20, 50), 3)))
            net_wt = Decimal(str(round(random.uniform(25, 40), 3)))  # >= 25gms
        else:
            ornament_type = random.choice(ORNAMENT_TYPES)
            # Realistic gold percentages: 22K = 91.67%, 18K = 75%, 14K = 58.33%
            percentage = Decimal(str(round(random.uniform(58, 95), 2)))
            # Weight varies by ornament type
            if ornament_type in ["Chain", "Necklace"]:
                gross_wt = Decimal(str(round(random.uniform(30, 150), 3)))
                net_wt = Decimal(str(round(random.uniform(25, 120), 3)))
            elif ornament_type in ["Bangle", "Bracelet"]:
                gross_wt = Decimal(str(round(random.uniform(20, 80), 3)))
                net_wt = Decimal(str(round(random.uniform(15, 65), 3)))
            elif ornament_type in ["Ring", "Earring", "Nose Pin"]:
                gross_wt = Decimal(str(round(random.uniform(2, 15), 3)))
                net_wt = Decimal(str(round(random.uniform(1.5, 12), 3)))
            else:
                gross_wt = Decimal(str(round(random.uniform(10, 100), 3)))
                net_wt = Decimal(str(round(random.uniform(8, 80), 3)))
        
        # Calculate stone weight (typically 5-15% of gross weight for studded jewelry)
        if random.random() < 0.3:  # 30% have stones
            stone_wt = gross_wt * Decimal("0.1")  # ~10% of gross weight
        else:
            stone_wt = Decimal("0")
        
        # Calculate loan value (typically 70-80% of collateral value)
        collateral_value = net_wt * Decimal("5500")  # Approx gold rate per gram
        loan_value = collateral_value * Decimal(str(round(random.uniform(0.70, 0.80), 2)))
        
        collateral = GoldCollateralDim(
            APP_ID=app_id,
            ACCOUNT_NUMBER=account_nums[i],
            ORNAMENT_TYPE=ornament_type,
            GROSS_WT=gross_wt,
            NET_WT=net_wt,
            PERCENTAGE=percentage,
            STONE_WT=Decimal(str(round(stone_wt, 3))),
            VALUATION_TYPE=random.choice(["Market", "Hallmark", "Appraisal", "BIS Certified"]),
            IMPUTIRY=Decimal(str(round(random.uniform(0, 5), 2))),
            SECURITY_TYPE="Gold",
            NO_UNITS=random.randint(1, 5),
            LOAN_VALUE=Decimal(str(round(loan_value, 2))),
            COLLATERAL_VALUE=Decimal(str(round(collateral_value, 2))),
            SOL_ID=f"SOL{random.randint(1, 100):03d}",
            LENDING_RATE=Decimal(str(round(random.uniform(9.0, 12.5), 4))),
            INSERTED_ON=inserted_on,
            LAST_UPDATED_TS=last_updated_ts,
        )
        collaterals.append(collateral)
    
    db.add_all(collaterals)
    db.commit()
    return collaterals


def populate_custom_freeze_details_dim(db: Session, customer_ids, account_nums):
    """Populate CUSTOM_FREEZE_DETAILS_DIM with realistic freeze data including Question 1 scenarios"""
    freezes = []
    
    # Question 1: Some customers with ReKYC due but NO RKYCF freeze code
    # We'll create freezes for some accounts, but NOT RKYCF for those with ReKYC due
    
    for i, (cust_id, accno) in enumerate(zip(customer_ids[:100], account_nums[:100])):
        inserted_on, last_updated_ts = _gen_audit_timestamps(stale_probability=0.15)  # 15% stale data
        
        # Only create freezes for 30% of accounts
        if random.random() > 0.7:
            # For Question 1: Don't create RKYCF freezes for first 20 customers (who have ReKYC due)
            if i < 20:
                frez_code = random.choice(["FRAUD", "COMPLIANCE", "KYC", "AML", "LEGAL", "OTHER"])
            else:
                frez_code = random.choice(list(FREEZE_CODES.keys()))
            
            frez_reason = FREEZE_CODES.get(frez_code, "Freeze")
            
            # Unfreeze logic
            unfrez_date = None
            unfrez_flg = "N"
            if random.random() > 0.5:  # 50% are unfrozen
                unfrez_date = datetime.now().date() - timedelta(days=random.randint(1, 30))
                unfrez_flg = "Y"
            
            freeze = CustomFreezeDetailsDim(
                FORACID=accno,
                CUST_ID=cust_id,
                FREZ_CODE=frez_code,
                FREZ_DATE=datetime.now().date() - timedelta(days=random.randint(1, 90)),
                UNFREZ_DATE=unfrez_date,
                UNFREZ_FLG=unfrez_flg,
                FREZ_REASON1=frez_reason,
                FREZ_REASON2=None,
                FREZ_REASON3=None,
                FREZ_REMARK1=f"Freeze reason: {frez_reason} for account {accno}",
                TYPE=random.choice(["DEBIT", "CREDIT", "BOTH"]),
                INIT_SOL_ID=f"SOL{random.randint(1, 100):03d}",
                DEL_FLG="N",
                INSERTED_ON=inserted_on,
                LAST_UPDATED_TS=last_updated_ts,
            )
            freezes.append(freeze)
    
    db.add_all(freezes)
    db.commit()
    return freezes


def generate_all_data(db: Session):
    """Generate all synthetic data for POC"""
    print("Generating synthetic data for POC...")
    
    # Generate IDs
    customer_ids = generate_customer_ids(100)
    cif_ids = generate_cif_ids(100)
    account_nums = generate_account_numbers("CA", 150)
    loan_accounts = generate_loan_accounts("LN", 200)
    app_ids = generate_app_ids(150)
    
    # Populate tables
    print("Populating SUPER_CUSTOMER_DIM...")
    populate_super_customer_dim(db, customer_ids)
    
    print("Populating CUSTOMER_NON_INDIVIDUAL_DIM...")
    populate_customer_non_individual_dim(db, customer_ids, cif_ids)
    
    print("Populating ACCOUNT_CA_DIM...")
    populate_account_ca_dim(db, customer_ids, cif_ids)
    
    print("Populating SUPER_LOAN_DIM...")
    populate_super_loan_dim(db, customer_ids)
    
    print("Populating SUPER_LOAN_ACCOUNT_DIM...")
    populate_super_loan_account_dim(db, loan_accounts)
    
    print("Populating CASELITE_LOAN_APPLICATIONS...")
    populate_caselite_loan_applications(db, app_ids)
    
    print("Populating GOLD_COLLATERAL_DIM...")
    populate_gold_collateral_dim(db, app_ids)
    
    print("Populating CUSTOM_FREEZE_DETAILS_DIM...")
    populate_custom_freeze_details_dim(db, customer_ids, account_nums)
    
    print("✅ All synthetic data generated successfully!")
    return True

