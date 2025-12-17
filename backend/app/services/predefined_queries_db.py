"""
Predefined Queries Service - Reads from Database
Replaces the hardcoded predefined_queries.py for production use
"""
from typing import Dict, Optional, List
from sqlalchemy.orm import Session
from app.database.schema import PredefinedQueries
from datetime import datetime


def get_all_predefined_queries(db: Session) -> List[Dict]:
    """Get all active predefined queries from database"""
    queries = db.query(PredefinedQueries).filter(
        PredefinedQueries.IS_ACTIVE == True
    ).all()
    
    return [
        {
            "key": q.QUERY_KEY,
            "question": q.QUESTION,
            "sql": q.SQL_QUERY,
            "description": q.DESCRIPTION
        }
        for q in queries
    ]


def get_predefined_query_by_key(db: Session, query_key: str) -> Optional[Dict]:
    """Get a specific predefined query by key"""
    query = db.query(PredefinedQueries).filter(
        PredefinedQueries.QUERY_KEY == query_key,
        PredefinedQueries.IS_ACTIVE == True
    ).first()
    
    if not query:
        return None
    
    return {
        "key": query.QUERY_KEY,
        "question": query.QUESTION,
        "sql": query.SQL_QUERY,
        "description": query.DESCRIPTION
    }


def match_question_to_predefined(db: Session, user_question: str) -> Optional[str]:
    """
    Match user question to predefined query by comparing against QUESTION field
    Returns the query_key if matched, None otherwise
    
    Uses STRICT matching strategy:
    1. Exact match (normalized - ignoring punctuation/whitespace)
    2. Very high similarity (98%+) with word-by-word comparison
    3. Identifies and validates key differentiating phrases dynamically
    
    This prevents false matches by being very strict - only matches when questions
    are essentially the same with minor variations (punctuation, case, spacing).
    """
    import re
    
    user_lower = user_question.lower().strip()

    # Extract comparison time thresholds like: "> 6 months", ">=2 month", "< 10 days"
    def extract_time_thresholds(text: str) -> set:
        # Keep operators and units
        pattern = re.compile(r'([<>]=?|=)\s*(\d+(?:\.\d+)?)\s*(day|days|month|months|year|years)\b', re.IGNORECASE)
        out = set()
        for op, num, unit in pattern.findall(text or ""):
            unit_norm = unit.lower()
            if unit_norm.endswith('s'):
                unit_norm = unit_norm[:-1]
            out.add((op, num, unit_norm))
        return out

    # Extract numeric tokens (used as a guardrail for similarity-matching)
    def extract_numbers(text: str) -> set:
        return set(re.findall(r'\b\d+(?:\.\d+)?\b', text or ""))
    
    # Normalize text for comparison (remove punctuation, normalize whitespace)
    def normalize_text(text: str) -> str:
        text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
        text = re.sub(r'[^\w\s]', ' ', text)  # Replace punctuation with space
        text = re.sub(r'\s+', ' ', text)  # Normalize again
        return text.strip()
    
    user_normalized = normalize_text(user_lower)
    user_words = set(word for word in user_normalized.split() if len(word) > 1)
    
    # Get all active queries
    queries = db.query(PredefinedQueries).filter(
        PredefinedQueries.IS_ACTIVE == True
    ).all()
    
    best_match = None
    best_similarity = 0.0
    
    for query in queries:
        question_lower = query.QUESTION.lower().strip()
        question_normalized = normalize_text(question_lower)
        question_words = set(word for word in question_normalized.split() if len(word) > 1)
        
        # 1. Exact match (normalized)
        if user_normalized == question_normalized:
            return query.QUERY_KEY
        
        # 2. Calculate similarity using Jaccard coefficient (intersection over union)
        if len(user_words) > 0 and len(question_words) > 0:
            common_words = user_words.intersection(question_words)
            union_words = user_words.union(question_words)
            similarity = len(common_words) / len(union_words) if union_words else 0.0
            
            # 3. Check for significant differences (words in one but not the other)
            user_only = user_words - question_words
            question_only = question_words - user_words
            
            # 4. Calculate difference ratio
            total_unique_words = len(user_only) + len(question_only)
            total_words = len(union_words)
            difference_ratio = total_unique_words / total_words if total_words > 0 else 1.0
            
            # 5. STRICT matching criteria:
            # - Must have 98%+ similarity (very strict)
            # - Difference ratio must be < 5% (very few different words)
            # - Must have at least 10 common words (ensures substantial overlap)
            # - Must have similar length (within 20% difference)
            length_ratio = min(len(user_words), len(question_words)) / max(len(user_words), len(question_words)) if max(len(user_words), len(question_words)) > 0 else 0
            
            if (similarity >= 0.98 and 
                difference_ratio < 0.05 and 
                len(common_words) >= 10 and
                length_ratio >= 0.8):
                # Guardrail: if the question contains numeric/time thresholds (e.g., ">2 months" vs ">6 months"),
                # do NOT allow a similarity match unless those thresholds match exactly.
                user_time = extract_time_thresholds(user_lower)
                q_time = extract_time_thresholds(question_lower)
                if user_time or q_time:
                    if user_time != q_time:
                        continue
                else:
                    user_nums = extract_numbers(user_lower)
                    q_nums = extract_numbers(question_lower)
                    if user_nums or q_nums:
                        if user_nums != q_nums:
                            continue

                # This is a very close match
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = query.QUERY_KEY
    
    # Only return if we found a very strong match
    return best_match if best_similarity >= 0.98 else None


def create_predefined_query(
    db: Session,
    query_key: str,
    question: str,
    sql_query: str,
    description: str,
    created_by: str = "system"
) -> PredefinedQueries:
    """Create a new predefined query"""
    query = PredefinedQueries(
        QUERY_KEY=query_key,
        QUESTION=question,
        SQL_QUERY=sql_query,
        DESCRIPTION=description,
        IS_ACTIVE=True,
        CREATED_DATE=datetime.now().date(),
        CREATED_BY=created_by
    )
    db.add(query)
    db.commit()
    db.refresh(query)
    return query


def update_predefined_query(
    db: Session,
    query_key: str,
    question: Optional[str] = None,
    sql_query: Optional[str] = None,
    description: Optional[str] = None,
    is_active: Optional[bool] = None,
    updated_by: str = "system"
) -> Optional[PredefinedQueries]:
    """Update an existing predefined query"""
    query = db.query(PredefinedQueries).filter(
        PredefinedQueries.QUERY_KEY == query_key
    ).first()
    
    if not query:
        return None
    
    if question is not None:
        query.QUESTION = question
    if sql_query is not None:
        query.SQL_QUERY = sql_query
    if description is not None:
        query.DESCRIPTION = description
    if is_active is not None:
        query.IS_ACTIVE = is_active
    
    query.UPDATED_DATE = datetime.now().date()
    query.UPDATED_BY = updated_by
    
    db.commit()
    db.refresh(query)
    return query

