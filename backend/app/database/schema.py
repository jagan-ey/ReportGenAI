"""
Database Schema Definitions for 8 BIU Star Schema Tables
"""
from sqlalchemy import Column, Integer, String, Date, DateTime, Numeric, Boolean, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class SuperCustomerDim(Base):
    """SUPER_CUSTOMER_DIM - Customer master data"""
    __tablename__ = 'super_customer_dim'
    
    CUST_ID = Column(String(50), primary_key=True)
    UCIC = Column(String(50), unique=True)
    CUST_NAME = Column(String(200))
    CLEAN_FULL_NAME = Column(String(200))
    CLEAN_FIRST_NAME = Column(String(100))
    CLEAN_LAST_NAME = Column(String(100))
    CLEAN_MOBILE = Column(String(15))
    PAN_NO = Column(String(10))
    CUST_DOB = Column(Date)
    GENDER = Column(String(10))
    RE_KYC_DUE_DATE = Column(Date)  # Critical for Question 1
    KYC_DATE = Column(Date)
    RETAIL_LAST_KYC_DATE = Column(Date)
    CORP_LAST_KYC_DATE = Column(Date)
    PRIMARY_SOL_ID = Column(String(10))
    STATE = Column(String(50))
    CITY = Column(String(50))
    CONSTITUTION_CODE = Column(String(10))
    CONSTITUTION_DESC_FINACLE = Column(String(100))
    STATUS = Column(String(20))
    SUSPENDED = Column(Boolean, default=False)
    BLACKLISTED = Column(Boolean, default=False)
    CURRENT_DT = Column(Date)
    INSERTED_ON = Column(DateTime)
    LAST_UPDATED_TS = Column(DateTime)


class CustomerNonIndividualDim(Base):
    """CUSTOMER_NON_INDIVIDUAL_DIM - Non-individual customer details"""
    __tablename__ = 'customer_non_individual_dim'
    
    CUST_ID = Column(String(50), primary_key=True)
    CIF_ID = Column(String(50), unique=True)
    CUST_NAME = Column(String(200))
    FIRST_NAME = Column(String(100))
    LAST_NAME = Column(String(100))
    MIDDLE_NAME = Column(String(100))
    PHONE_NUMBER = Column(String(15))  # Critical for Question 2
    EMAIL_ID = Column(String(100))
    PAN = Column(String(10))
    IEC = Column(String(20))  # Critical for Question 4
    CONSTITUTION_CODE = Column(String(10))  # Critical for Question 7
    CONSTITUTION_DESC = Column(String(100))
    OPENING_DATE = Column(Date)
    PRIMARY_SOL_ID = Column(String(10))
    STATE = Column(String(50))
    CITY = Column(String(50))
    REKYC_DUE_DATE = Column(Date)
    LATEST_KYC_DATE = Column(Date)
    STATUS = Column(String(20))
    INSERTED_ON = Column(DateTime)
    LAST_UPDATED_TS = Column(DateTime)


class AccountCaDim(Base):
    """ACCOUNT_CA_DIM - Current Account details"""
    __tablename__ = 'account_ca_dim'
    
    ACCT_SKEY = Column(Integer, primary_key=True, autoincrement=True)
    ACCT_NUM = Column(String(50), unique=True)
    CUST_ID = Column(String(50), ForeignKey('customer_non_individual_dim.CUST_ID'))
    ACCT_NAME = Column(String(200))
    SCHEME_CODE = Column(String(20))  # Critical for Question 4 (CAGBL)
    SCHEME_DESC = Column(String(200))
    ACCT_OPN_DATE = Column(Date)
    ACCT_STATUS = Column(String(20))
    DEBIT_FREZ_FLAG = Column(Boolean, default=False)
    DEBIT_FREZ_DATE = Column(Date)
    DEBIT_FREZ_REASON_CODE = Column(String(20))
    SOL_ID = Column(String(10))
    BALANCE = Column(Numeric(18, 2))
    SANCT_LIM = Column(Numeric(18, 2))
    CURRENT_DT = Column(Date)
    INSERTED_ON = Column(DateTime)
    LAST_UPDATED_TS = Column(DateTime)


class SuperLoanDim(Base):
    """SUPER_LOAN_DIM - Loan account master"""
    __tablename__ = 'super_loan_dim'
    
    ACID = Column(Integer, primary_key=True, autoincrement=True)
    ACCNO = Column(String(50), unique=True)
    CUSTID = Column(String(50), ForeignKey('super_customer_dim.CUST_ID'))
    NAME = Column(String(200))
    PRODUCT_ID = Column(String(50))  # Critical for Question 7 (Tractor)
    DESCRIPTION = Column(String(200))
    SCHEME = Column(String(50))
    STYPE = Column(String(50))
    BALANCE = Column(Numeric(18, 2))
    SANCT_LIM = Column(Numeric(18, 2))
    INT_RATE = Column(Numeric(8, 4))
    FREZ_CODE = Column(String(20))
    ACCT_OPN_DATE = Column(Date)
    ACCT_CLS_DATE = Column(Date)
    ACCT_CLS_FLG = Column(String(1))
    SOL_ID = Column(String(10))
    STATE = Column(String(50))
    CURRENCY = Column(String(3))
    TYPE_ADVANCE_CODE = Column(String(20))
    ACCT_LABEL = Column(String(100))
    INSERTED_ON = Column(DateTime)
    LAST_UPDATED_TS = Column(DateTime)


class SuperLoanAccountDim(Base):
    """SUPER_LOAN_ACCOUNT_DIM - Detailed loan account information"""
    __tablename__ = 'super_loan_account_dim'
    
    ACCNO = Column(String(50), primary_key=True)
    CUSTID = Column(String(50))
    NAME = Column(String(200))
    SCHEME = Column(String(50))
    PRODUCT_ID = Column(String(50))
    INSTALTYPE = Column(String(20))  # Critical for Question 3 (monthly)
    INSTLMODE = Column(String(20))
    EMI = Column(Numeric(18, 2))
    TENURE = Column(Integer)  # In months - Critical for Question 3
    EMI_START_DT = Column(Date)
    NEXT_INSTALLMENT_DATE = Column(Date)
    INT_RATE = Column(Numeric(8, 4))
    BALANCE = Column(Numeric(18, 2))
    SANCT_LIM = Column(Numeric(18, 2))
    FREZ_CODE = Column(String(20))
    ACCT_OPN_DATE = Column(Date)
    MATURITY_DATE = Column(Date)
    SOL_ID = Column(String(10))
    STATE = Column(String(50))
    INSERTED_ON = Column(DateTime)
    LAST_UPDATED_TS = Column(DateTime)


class CaseliteLoanApplications(Base):
    """CASELITE_LOAN_APPLICATIONS - Gold loan application details"""
    __tablename__ = 'caselite_loan_applications'
    
    APP_ID = Column(String(50), primary_key=True)
    CAS_LITE_ID = Column(String(50))
    FIN_CIF_NUMBER = Column(String(50))
    FIN_LOAN_ACCOUNT_NUMBER = Column(String(50))
    SCHEME_NAME = Column(String(50))  # Critical for Question 3 (LRGMI)
    PRODUCT = Column(String(50))  # Critical for Question 3 (non-agricultural)
    TENURE = Column(Integer)  # In months - Critical for Question 3
    LENDING_RATE = Column(Numeric(8, 4))
    AGREED_LN_AMT = Column(Numeric(18, 2))
    NET_DISB_AMT = Column(Numeric(18, 2))
    APPLIED_DATE_LED = Column(Date)
    APPROVED_ON = Column(Date)
    STAGE_STATUS = Column(String(50))
    SOL_ID = Column(String(10))
    FIRST_NAME = Column(String(100))
    LAST_NAME = Column(String(100))
    MOBILE_NO = Column(String(15))
    PAN_NO = Column(String(10))
    CIBIL_SCORE = Column(Integer)
    ACTIVE_IND = Column(String(1))
    INSERTED_ON = Column(DateTime)
    LAST_UPDATED_TS = Column(DateTime)


class GoldCollateralDim(Base):
    """GOLD_COLLATERAL_DIM - Gold collateral/ornament details"""
    __tablename__ = 'gold_collateral_dim'
    
    APP_ID = Column(String(50), primary_key=True)
    ACCOUNT_NUMBER = Column(String(50))
    ORNAMENT_TYPE = Column(String(50))  # Critical for Questions 5 & 6 (Mangalsutra)
    GROSS_WT = Column(Numeric(10, 3))  # Critical for Questions 5 & 6
    NET_WT = Column(Numeric(10, 3))  # Critical for Question 6
    PERCENTAGE = Column(Numeric(5, 2))  # Gold percentage - Critical for Question 5
    STONE_WT = Column(Numeric(10, 3))
    VALUATION_TYPE = Column(String(50))
    IMPUTIRY = Column(Numeric(5, 2))
    SECURITY_TYPE = Column(String(50))
    NO_UNITS = Column(Integer)
    LOAN_VALUE = Column(Numeric(18, 2))
    COLLATERAL_VALUE = Column(Numeric(18, 2))
    SOL_ID = Column(String(10))
    LENDING_RATE = Column(Numeric(8, 4))
    INSERTED_ON = Column(DateTime)
    LAST_UPDATED_TS = Column(DateTime)


class CustomFreezeDetailsDim(Base):
    """CUSTOM_FREEZE_DETAILS_DIM - Account freeze details"""
    __tablename__ = 'custom_freeze_details_dim'
    
    SRL_NUM = Column(Integer, primary_key=True, autoincrement=True)
    FORACID = Column(String(50))  # Account Number
    CUST_ID = Column(String(50))
    FREZ_CODE = Column(String(20))  # Critical for Question 1 (RKYCF)
    FREZ_DATE = Column(Date)
    UNFREZ_DATE = Column(Date)
    UNFREZ_FLG = Column(String(1))
    FREZ_REASON1 = Column(String(100))
    FREZ_REASON2 = Column(String(100))
    FREZ_REASON3 = Column(String(100))
    FREZ_REMARK1 = Column(Text)
    TYPE = Column(String(20))
    INIT_SOL_ID = Column(String(10))
    DEL_FLG = Column(String(1))
    INSERTED_ON = Column(DateTime)
    LAST_UPDATED_TS = Column(DateTime)


class PredefinedQueries(Base):
    """PREDEFINED_QUERIES - Store predefined queries in database"""
    __tablename__ = 'predefined_queries'
    
    QUERY_ID = Column(Integer, primary_key=True, autoincrement=True)
    QUERY_KEY = Column(String(50), unique=True, nullable=False)  # e.g., "rekyc_freeze"
    QUESTION = Column(Text, nullable=False)  # The question text (used for matching)
    SQL_QUERY = Column(Text, nullable=False)  # The SQL query
    DESCRIPTION = Column(String(500))  # Description of what the query does
    IS_ACTIVE = Column(Boolean, default=True)  # Enable/disable query
    CREATED_DATE = Column(Date)
    UPDATED_DATE = Column(Date)
    CREATED_BY = Column(String(50))
    UPDATED_BY = Column(String(50))

