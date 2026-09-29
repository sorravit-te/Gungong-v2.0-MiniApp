"""History and cache management router."""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.database_service import get_database_service
from ..core.models import COLLECTION_HISTORY

router = APIRouter()


class FeedbackRequest(BaseModel):
    """Request model for submitting feedback."""
    history_id: str
    user_id: str
    feedback_type: str  # 'like' or 'dislike'
    comment: Optional[str] = None


@router.get("/history/{entry_id}")
async def get_history_entry(entry_id: str):
    """Get a single history entry by ID."""
    try:
        db_service = get_database_service()
        if not db_service:
            raise HTTPException(status_code=503, detail="Database not configured")

        doc_ref = db_service.db.collection(COLLECTION_HISTORY).document(entry_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="History entry not found")
            
        data = doc.to_dict()
        
        # Safe date conversion
        created_at = data.get("created_at")
        if created_at and hasattr(created_at, 'isoformat'):
            created_at = created_at.isoformat()
        elif created_at:
            created_at = str(created_at)
            
        expires_at = data.get("expires_at")
        if expires_at and hasattr(expires_at, 'isoformat'):
            expires_at = expires_at.isoformat()
        elif expires_at:
            expires_at = str(expires_at)

        return {
            "id": doc.id,
            "message_hash": data.get("message_hash"),
            "message_text": data.get("message_text", ""),
            "full_message": data.get("message_text", ""),
            "classification": data.get("classification"),
            "is_fraud": data.get("is_fraud"),
            "is_safe": data.get("is_safe"),
            "confidence_score": data.get("confidence_score"),
            "reason": data.get("reason"),
            "reasoning_summary": data.get("reasoning_summary"),
            "keywords_found": data.get("keywords_found", []),
            "url_check_result": data.get("url_check_result"),
            "has_malicious_urls": data.get("has_malicious_urls"),
            "hit_count": data.get("hit_count", 0),
            "created_at": created_at,
            "expires_at": expires_at,
            "type": data.get("type", "unknown")
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Error fetching history entry {entry_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache-entries")
async def get_cache_entries(limit: int = 20, offset: int = 0, user_id: Optional[str] = None):
    """Get paginated cache entries (history)."""
    db_service = get_database_service()

    if not db_service:
        raise HTTPException(
            status_code=503,
            detail="Database not configured. Please set DATABASE_URL in .env"
        )

    try:
        from google.cloud import firestore
        
        # Use Firestore collection
        collection = db_service.db.collection(COLLECTION_HISTORY)
        
        # Base query
        query = collection
        if user_id:
             query = query.where(filter=firestore.FieldFilter("user_id", "==", user_id))

        # Get total count
        total_query = query.count()
        total_snapshot = total_query.get()
        total = total_snapshot[0][0].value
        
        # Get entries with pagination
        query = query.order_by("created_at", direction=firestore.Query.DESCENDING).limit(limit).offset(offset)
        
        # Optimization: Select only necessary fields
        query = query.select([
            "message_text", "classification", "is_fraud", "is_safe", 
            "confidence_score", "reason", "reasoning_summary", 
            "keywords_found", "has_malicious_urls", "hit_count", 
            "created_at", "expires_at", "type"
        ])

        docs = query.stream()
        
        entries_list = []
        for doc in docs:
            try:
                data = doc.to_dict()
                
                # Safe date conversion
                created_at = data.get("created_at")
                if created_at and hasattr(created_at, 'isoformat'):
                    created_at = created_at.isoformat()
                elif created_at:
                    created_at = str(created_at)
                    
                expires_at = data.get("expires_at")
                if expires_at and hasattr(expires_at, 'isoformat'):
                    expires_at = expires_at.isoformat()
                elif expires_at:
                    expires_at = str(expires_at)

                entries_list.append({
                    "id": doc.id,
                    "message_hash": data.get("message_hash"),
                    "message_text": data.get("message_text", "")[:100] + "..." if len(data.get("message_text", "")) > 100 else data.get("message_text", ""),
                    "full_message": data.get("message_text", ""),
                    "classification": data.get("classification"),
                    "is_fraud": data.get("is_fraud"),
                    "is_safe": data.get("is_safe"),
                    "confidence_score": data.get("confidence_score"),
                    "reason": data.get("reason"),
                    "reasoning_summary": data.get("reasoning_summary"),
                    "keywords_found": data.get("keywords_found", []),
                    "url_check_result": data.get("url_check_result"),
                    "has_malicious_urls": data.get("has_malicious_urls"),
                    "hit_count": data.get("hit_count", 0),
                    "created_at": created_at,
                    "expires_at": expires_at,
                    "type": data.get("type", "unknown")
                })
            except Exception as e:
                print(f"⚠️ Error processing history entry {doc.id}: {e}")
                continue

        result = {
            "total": total,
            "limit": limit,
            "offset": offset,
            "entries": entries_list
        }

        return result

    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error fetching cache entries: {error_msg}")
        
        if "requires an index" in error_msg:
            raise HTTPException(
                status_code=400, 
                detail=f"Database index required. Please create it using the link in the server logs or contact administrator. Error: {error_msg}"
            )
            
        raise HTTPException(status_code=500, detail=error_msg)


@router.get("/cache-stats")
async def cache_stats():
    """
    Get cache statistics from database.

    Returns:
        {
            "total_entries": 10,
            "active_entries": 8,
            "expired_entries": 2,
            "total_cache_hits": 45
        }
    """
    db_service = get_database_service()

    if not db_service:
        raise HTTPException(
            status_code=503,
            detail="Database not configured. Please set DATABASE_URL in .env"
        )

    try:
        stats = db_service.get_cache_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get cache stats: {str(e)}")


@router.post("/feedback")
async def submit_feedback(request: FeedbackRequest):
    """Submit user feedback for a history entry."""
    db_service = get_database_service()
    if not db_service:
        raise HTTPException(status_code=503, detail="Database not configured")

    success = db_service.save_feedback(
        history_id=request.history_id,
        user_id=request.user_id,
        feedback_type=request.feedback_type,
        comment=request.comment
    )

    if success:
        return {"status": "success", "message": "Feedback saved"}
    else:
        raise HTTPException(status_code=500, detail="Failed to save feedback")
