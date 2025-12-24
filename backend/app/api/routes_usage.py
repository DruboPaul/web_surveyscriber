"""
Usage Report API Routes - Track and download API token usage reports.

Provides endpoints for:
- Saving token usage after each job
- Getting usage summary by period (weekly, monthly)
- Downloading usage reports as CSV
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
import io
import csv

from backend.app.db.database import get_session_local
from backend.app.db.models import UsageHistory

router = APIRouter(tags=["Usage"])


class UsageRecordCreate(BaseModel):
    """Request to save usage record."""
    batch_id: str
    job_id: Optional[str] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: Optional[str] = None
    provider: Optional[str] = None
    images_processed: int = 1


@router.post("/record")
def save_usage_record(record: UsageRecordCreate):
    """Save a usage record after extraction job completes."""
    SessionLocal = get_session_local()
    session = SessionLocal()
    
    try:
        # Calculate estimated cost
        cost_cents = UsageHistory.estimate_cost(record.total_tokens, record.model or "gpt-4o")
        
        usage = UsageHistory(
            batch_id=record.batch_id,
            job_id=record.job_id,
            prompt_tokens=record.prompt_tokens,
            completion_tokens=record.completion_tokens,
            total_tokens=record.total_tokens,
            model=record.model,
            provider=record.provider,
            images_processed=record.images_processed,
            estimated_cost_cents=cost_cents
        )
        
        session.add(usage)
        session.commit()
        
        return {
            "success": True,
            "message": "Usage recorded",
            "estimated_cost_usd": cost_cents / 100.0
        }
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/summary")
def get_usage_summary(
    period: str = Query("weekly", description="Period: 'weekly', 'monthly', or 'all'"),
    provider: Optional[str] = None
):
    """Get usage summary for the specified period."""
    SessionLocal = get_session_local()
    session = SessionLocal()
    
    try:
        # Calculate date range
        now = datetime.utcnow()
        if period == "weekly":
            start_date = now - timedelta(days=7)
        elif period == "monthly":
            start_date = now - timedelta(days=30)
        else:
            start_date = None
        
        # Build query
        query = session.query(UsageHistory)
        if start_date:
            query = query.filter(UsageHistory.created_at >= start_date)
        if provider:
            query = query.filter(UsageHistory.provider == provider)
        
        records = query.order_by(UsageHistory.created_at.desc()).all()
        
        # Aggregate totals
        total_tokens = sum(r.total_tokens for r in records)
        total_cost_cents = sum(r.estimated_cost_cents for r in records)
        total_images = sum(r.images_processed for r in records)
        
        # Group by date
        daily_breakdown = {}
        for r in records:
            date_str = r.created_at.strftime("%Y-%m-%d") if r.created_at else "Unknown"
            if date_str not in daily_breakdown:
                daily_breakdown[date_str] = {"tokens": 0, "cost_cents": 0, "images": 0, "jobs": 0}
            daily_breakdown[date_str]["tokens"] += r.total_tokens
            daily_breakdown[date_str]["cost_cents"] += r.estimated_cost_cents
            daily_breakdown[date_str]["images"] += r.images_processed
            daily_breakdown[date_str]["jobs"] += 1
        
        return {
            "period": period,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": now.isoformat(),
            "total_jobs": len(records),
            "total_images": total_images,
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost_cents / 100.0, 4),
            "daily_breakdown": daily_breakdown
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/report/download")
def download_usage_report(
    period: str = Query("monthly", description="Period: 'weekly', 'monthly', or 'all'"),
    format: str = Query("csv", description="Format: 'csv'")
):
    """Download usage report as CSV file."""
    SessionLocal = get_session_local()
    session = SessionLocal()
    
    try:
        # Calculate date range
        now = datetime.utcnow()
        if period == "weekly":
            start_date = now - timedelta(days=7)
            period_label = "Last 7 Days"
        elif period == "monthly":
            start_date = now - timedelta(days=30)
            period_label = "Last 30 Days"
        else:
            start_date = None
            period_label = "All Time"
        
        # Query records
        query = session.query(UsageHistory)
        if start_date:
            query = query.filter(UsageHistory.created_at >= start_date)
        records = query.order_by(UsageHistory.created_at.desc()).all()
        
        # Generate CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([f"SurveyScriber API Usage Report - {period_label}"])
        writer.writerow([f"Generated: {now.strftime('%Y-%m-%d %H:%M:%S')}"])
        writer.writerow([])
        
        # Summary
        total_tokens = sum(r.total_tokens for r in records)
        total_cost_cents = sum(r.estimated_cost_cents for r in records)
        total_images = sum(r.images_processed for r in records)
        
        writer.writerow(["SUMMARY"])
        writer.writerow(["Total Jobs", len(records)])
        writer.writerow(["Total Images Processed", total_images])
        writer.writerow(["Total Tokens Used", f"{total_tokens:,}"])
        writer.writerow(["Estimated Cost (USD)", f"${total_cost_cents / 100.0:.4f}"])
        writer.writerow([])
        
        # Detailed records
        writer.writerow(["DETAILED RECORDS"])
        writer.writerow(["Date", "Batch ID", "Images", "Prompt Tokens", "Completion Tokens", "Total Tokens", "Model", "Provider", "Est. Cost (USD)"])
        
        for r in records:
            writer.writerow([
                r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
                r.batch_id or "",
                r.images_processed,
                r.prompt_tokens,
                r.completion_tokens,
                r.total_tokens,
                r.model or "",
                r.provider or "",
                f"${r.estimated_cost_cents / 100.0:.4f}"
            ])
        
        # Prepare response
        output.seek(0)
        filename = f"surveyscriber_usage_{period}_{now.strftime('%Y%m%d')}.csv"
        
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.delete("/clear")
def clear_usage_history(
    period: str = Query("all", description="Period to clear: 'old' (>30 days) or 'all'")
):
    """Clear usage history records."""
    SessionLocal = get_session_local()
    session = SessionLocal()
    
    try:
        if period == "old":
            # Delete records older than 30 days
            cutoff_date = datetime.utcnow() - timedelta(days=30)
            deleted = session.query(UsageHistory).filter(
                UsageHistory.created_at < cutoff_date
            ).delete()
        else:
            # Delete all records
            deleted = session.query(UsageHistory).delete()
        
        session.commit()
        
        return {
            "success": True,
            "message": f"Deleted {deleted} usage records",
            "deleted_count": deleted
        }
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
