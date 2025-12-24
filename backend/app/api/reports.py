"""
Report Management API endpoints
Handles report download, approval, and scheduling
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.user import ApprovalRequest as ApprovalRequestModel, ScheduledReport as ScheduledReportModel
from app.services.auth import get_user_by_username
from app.services.predefined_queries_db import create_predefined_query, get_all_predefined_queries
from datetime import datetime, timedelta
import json
import re
import logging
import traceback

logger = logging.getLogger(__name__)

router = APIRouter()


# User context - queries database for user information
def get_current_user(
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    db: Session = Depends(get_db)
):
    """
    Get current user from header and query database
    In production, this would validate JWT token or session
    """
    if x_user_id:
        from app.services.auth import get_user_by_username
        user = get_user_by_username(db, x_user_id)
        
        if user and user.IS_ACTIVE:
            return {
                "user_id": user.USER_ID,
                "username": user.USERNAME,
                "email": user.EMAIL,
                "role": user.ROLE,
                "full_name": user.FULL_NAME,
                "department": user.DEPARTMENT
            }
    
    # Default user if not found or not provided
    return {
        "user_id": 0,
        "username": "system",
        "email": "system@bank.com",
        "role": "user",
        "full_name": "System User",
        "department": None
    }


class ApprovalRequest(BaseModel):
    query: str
    data: List[Dict[str, Any]]
    row_count: int
    question: str
    approver_email: Optional[str] = None
    notes: Optional[str] = None


class ScheduleRequest(BaseModel):
    query: str
    question: str
    schedule_type: str  # "daily", "weekly", "monthly"
    schedule_time: Optional[str] = None  # HH:MM format
    recipients: Optional[List[str]] = None
    enabled: bool = True


@router.post("/send-approval")
async def send_for_approval(
    request: ApprovalRequest, 
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Send report for approval workflow
    Stores approval request in database with user context
    """
    try:
        # Generate approval ID
        approval_id = f"APPROVAL-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        logger.debug(f"Creating approval request: {approval_id}")
        logger.debug(f"Requested by: {current_user['username']}")
        logger.debug(f"Approver email: {request.approver_email}")
        
        # Store approval request in database
        approval_record = ApprovalRequestModel(
            REQUEST_ID=approval_id,
            REQUESTED_BY=current_user["username"],
            QUERY=request.query,
            QUESTION=request.question,
            ROW_COUNT=request.row_count,
            STATUS='pending',
            APPROVER_EMAIL=request.approver_email,
            NOTES=request.notes,
            CREATED_DATE=datetime.now()
        )
        
        db.add(approval_record)
        db.commit()
        db.refresh(approval_record)
        
        logger.debug(f"Approval request saved successfully: {approval_id}")
        
        # In production, this would also:
        # 1. Send email notification to approver
        # 2. Create workflow entry in workflow system
        # 3. Log audit trail
        
        return {
            "status": "success",
            "message": "Report sent for approval successfully",
            "approval_id": approval_id,
            "requested_by": current_user["username"],
            "status": "pending",
            "timestamp": datetime.now().isoformat(),
            "query": request.query,
            "row_count": request.row_count
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating approval: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error sending for approval: {str(e)}")


@router.post("/schedule")
async def schedule_report(
    request: ScheduleRequest, 
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Schedule a report for recurring execution
    Stores schedule in database with user context
    """
    try:
        # Generate schedule ID
        schedule_id = f"SCHEDULE-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Validate schedule type
        if request.schedule_type not in ["daily", "weekly", "monthly"]:
            raise HTTPException(status_code=400, detail="Invalid schedule_type. Must be: daily, weekly, or monthly")
        
        # Calculate next run time
        now = datetime.now()
        if request.schedule_time:
            # Parse time (HH:MM)
            hour, minute = map(int, request.schedule_time.split(':'))
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= now:
                if request.schedule_type == "daily":
                    next_run += timedelta(days=1)
                elif request.schedule_type == "weekly":
                    next_run += timedelta(weeks=1)
                elif request.schedule_type == "monthly":
                    next_run += timedelta(days=30)
        else:
            # Default: run tomorrow at same time
            next_run = now + timedelta(days=1)
        
        # Store schedule in database
        schedule_record = ScheduledReportModel(
            SCHEDULE_KEY=schedule_id,
            CREATED_BY=current_user["username"],
            QUERY=request.query,
            QUESTION=request.question,
            SCHEDULE_TYPE=request.schedule_type,
            SCHEDULE_TIME=request.schedule_time or "09:00",
            RECIPIENTS=json.dumps(request.recipients or [current_user["email"]]),
            IS_ENABLED=request.enabled,
            NEXT_RUN=next_run,
            CREATED_DATE=datetime.now()
        )
        
        db.add(schedule_record)
        db.commit()
        db.refresh(schedule_record)
        
        # In production, this would also:
        # 1. Set up cron job or scheduled task (Celery, APScheduler, etc.)
        # 2. Configure email service for recipients
        # 3. Create monitoring/alerting
        
        return {
            "status": "success",
            "message": f"Report scheduled for {request.schedule_type} execution",
            "schedule_id": schedule_id,
            "created_by": current_user["username"],
            "schedule_type": request.schedule_type,
            "next_run": next_run.isoformat(),
            "enabled": request.enabled,
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error scheduling report: {str(e)}")


@router.get("/schedules")
async def list_schedules(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    List all scheduled reports for the current user
    """
    try:
        schedules = db.query(ScheduledReportModel).filter(
            ScheduledReportModel.CREATED_BY == current_user["username"]
        ).order_by(ScheduledReportModel.CREATED_DATE.desc()).all()
        
        return {
            "schedules": [
                {
                    "schedule_id": s.SCHEDULE_KEY,
                    "question": s.QUESTION,
                    "schedule_type": s.SCHEDULE_TYPE,
                    "schedule_time": s.SCHEDULE_TIME,
                    "enabled": s.IS_ENABLED,
                    "next_run": s.NEXT_RUN.isoformat() if s.NEXT_RUN else None,
                    "last_run": s.LAST_RUN.isoformat() if s.LAST_RUN else None,
                    "created_date": s.CREATED_DATE.isoformat(),
                    "recipients": json.loads(s.RECIPIENTS) if s.RECIPIENTS else []
                }
                for s in schedules
            ],
            "count": len(schedules)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching schedules: {str(e)}")


@router.get("/approvers")
async def list_approvers(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    List all available approvers (only users with role 'approver', not 'admin')
    In production, this would fetch from user database with approver role only
    """
    try:
        # Query database for users with role 'approver' only (not admin)
        from app.models.user import User
        approver_users = db.query(User).filter(
            User.ROLE == 'approver',
            User.IS_ACTIVE == True
        ).all()
        
        approvers = [
            {
                "user_id": user.USER_ID,
                "username": user.USERNAME,
                "name": user.FULL_NAME or user.USERNAME,
                "email": user.EMAIL,
                "role": user.ROLE,
                "department": user.DEPARTMENT
            }
            for user in approver_users
        ]
        
        # If no approvers found in DB, return empty list (or fallback for POC)
        if len(approvers) == 0:
            # Fallback for POC if database doesn't have approvers yet
            approvers = [
                {
                    "user_id": "approver.user",
                    "username": "approver.user",
                    "name": "Approver User",
                    "email": "approver@bank.com",
                    "role": "approver",
                    "department": "Risk Management"
                },
                {
                    "user_id": "manager.smith",
                    "username": "manager.smith",
                    "name": "Manager Smith",
                    "email": "manager.smith@bank.com",
                    "role": "approver",
                    "department": "Compliance"
                },
                {
                    "user_id": "senior.approver",
                    "username": "senior.approver",
                    "name": "Senior Approver",
                    "email": "senior.approver@bank.com",
                    "role": "approver",
                    "department": "Audit"
                }
            ]
        
        return {
            "approvers": approvers,
            "count": len(approvers)
        }
    except Exception as e:
        logger.error(f"Error fetching approvers: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching approvers: {str(e)}")


@router.get("/approvals")
async def list_approvals(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    status: Optional[str] = None
):
    """
    List approval requests
    - If user is requester: shows their requests
    - If user is approver: shows all requests (pending by default)
    """
    try:
        logger.debug(f"Current user: {current_user}, role: {current_user.get('role')}, status filter: {status}")
        
        query = db.query(ApprovalRequestModel)
        
        # Filter by user role
        user_role = current_user.get("role", "user")
        
        if user_role == "approver" or user_role == "admin":
            # Approvers see all requests (optionally filtered by status)
            # If no status specified, show pending by default
            if status:
                query = query.filter(ApprovalRequestModel.STATUS == status)
            else:
                # Default to pending for approvers if no status specified
                query = query.filter(ApprovalRequestModel.STATUS == "pending")
        else:
            # Regular users see only their requests
            query = query.filter(ApprovalRequestModel.REQUESTED_BY == current_user["username"])
            if status:
                query = query.filter(ApprovalRequestModel.STATUS == status)
        
        approvals = query.order_by(ApprovalRequestModel.CREATED_DATE.desc()).all()
        
        logger.debug(f"Found {len(approvals)} approvals")
        
        return {
            "approvals": [
                {
                    "approval_id": a.REQUEST_ID,
                    "question": a.QUESTION,
                    "query": a.QUERY,  # Include SQL query
                    "requested_by": a.REQUESTED_BY,
                    "status": a.STATUS,
                    "row_count": a.ROW_COUNT,
                    "created_date": a.CREATED_DATE.isoformat() if a.CREATED_DATE else None,
                    "approved_date": a.APPROVED_DATE.isoformat() if a.APPROVED_DATE else None,
                    "approved_by": a.APPROVED_BY,
                    "notes": a.NOTES
                }
                for a in approvals
            ],
            "count": len(approvals)
        }
    except Exception as e:
        logger.error(f"Error fetching approvals: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching approvals: {str(e)}")


@router.post("/approvals/{approval_id}/approve")
async def approve_request(
    approval_id: str,
    notes: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Approve a pending request (requires approver role)
    Automatically adds the approved query to predefined queries for future use
    """
    if current_user["role"] not in ["approver", "admin"]:
        raise HTTPException(status_code=403, detail="Only approvers can approve requests")
    
    try:
        approval = db.query(ApprovalRequestModel).filter(
            ApprovalRequestModel.REQUEST_ID == approval_id
        ).first()
        
        if not approval:
            raise HTTPException(status_code=404, detail="Approval request not found")
        
        if approval.STATUS != "pending":
            raise HTTPException(status_code=400, detail=f"Request is already {approval.STATUS}")
        
        # Update approval status
        approval.STATUS = "approved"
        approval.APPROVED_BY = current_user["username"]
        approval.APPROVED_DATE = datetime.now()
        approval.NOTES = notes
        
        # Initialize variables
        query_key = None
        added_to_predefined = False
        
        # Add to predefined queries
        try:
            # Validate required fields
            if not approval.QUESTION or not approval.QUERY:
                raise ValueError("Approval request missing QUESTION or QUERY")
            
            # Generate a unique query_key from the question
            # Use first few words of question, sanitized, with timestamp for uniqueness
            question_words = re.findall(r'\b\w+\b', approval.QUESTION.lower())[:5]  # First 5 words
            base_key = '_'.join(question_words) if question_words else 'approved_query'
            base_key = re.sub(r'[^a-z0-9_]', '', base_key)  # Remove special chars
            base_key = base_key[:30]  # Limit length
            
            # Check if key already exists, append timestamp if needed
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            query_key = f"{base_key}_{timestamp}"
            
            # Ensure uniqueness by checking existing queries
            existing_queries = get_all_predefined_queries(db)
            existing_keys = {q['key'] for q in existing_queries}
            counter = 1
            while query_key in existing_keys:
                query_key = f"{base_key}_{timestamp}_{counter}"
                counter += 1
            
            # Create user-friendly description
            # The description is displayed as the title in the UI, so use the question itself
            # This makes it clean and user-friendly instead of showing technical metadata
            if approval.QUESTION:
                # Use the question as the description (it's already user-friendly and natural)
                description = approval.QUESTION
            else:
                # Fallback: create a simple description from SQL query
                sql_lower = approval.QUERY.lower() if approval.QUERY else ""
                if "select" in sql_lower and "from" in sql_lower:
                    # Try to extract table names for a basic description
                    table_match = re.search(r'from\s+(\w+)', sql_lower, re.IGNORECASE)
                    if table_match:
                        table_name = table_match.group(1)
                        description = f"Query on {table_name} table"
                    else:
                        description = "Approved query"
                else:
                    description = "Approved query"
            
            # Create predefined query
            predefined_query = create_predefined_query(
                db=db,
                query_key=query_key,
                question=approval.QUESTION,
                sql_query=approval.QUERY,
                description=description,
                created_by=current_user["username"]
            )
            
            added_to_predefined = True
            logger.info(f"Added approved query to predefined queries: {query_key}, Question: {approval.QUESTION[:100]}, SQL length: {len(approval.QUERY)} chars")
            
        except Exception as e:
            # Log error but don't fail the approval
            error_msg = str(e)
            logger.warning(f"Failed to add query to predefined queries: {error_msg}, Approval ID: {approval_id}, Question: {approval.QUESTION if approval.QUESTION else 'None'}, Query length: {len(approval.QUERY) if approval.QUERY else 0} chars", exc_info=True)
            # Continue with approval even if adding to predefined queries fails
        
        # Commit approval status change
        db.commit()
        
        return {
            "status": "success",
            "message": "Request approved successfully" + (" and added to predefined queries" if added_to_predefined else ""),
            "approval_id": approval_id,
            "approved_by": current_user["username"],
            "query_key": query_key,
            "added_to_predefined": added_to_predefined
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error approving request: {str(e)}")


@router.post("/approvals/{approval_id}/reject")
async def reject_request(
    approval_id: str,
    notes: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Reject a pending request (requires approver role)
    """
    if current_user["role"] not in ["approver", "admin"]:
        raise HTTPException(status_code=403, detail="Only approvers can reject requests")
    
    try:
        approval = db.query(ApprovalRequestModel).filter(
            ApprovalRequestModel.REQUEST_ID == approval_id
        ).first()
        
        if not approval:
            raise HTTPException(status_code=404, detail="Approval request not found")
        
        if approval.STATUS != "pending":
            raise HTTPException(status_code=400, detail=f"Request is already {approval.STATUS}")
        
        approval.STATUS = "rejected"
        approval.APPROVED_BY = current_user["username"]
        approval.APPROVED_DATE = datetime.now()
        approval.NOTES = notes
        
        db.commit()
        
        return {
            "status": "success",
            "message": "Request rejected",
            "approval_id": approval_id,
            "rejected_by": current_user["username"]
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error rejecting request: {str(e)}")
