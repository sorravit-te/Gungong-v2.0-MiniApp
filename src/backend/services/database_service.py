"""Database service for fraud detection cache using Google Cloud Firestore."""

import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from google.cloud import firestore
from google.oauth2 import service_account
import os

from ..core.config import settings
from ..core.models import (
    COLLECTION_FRAUD_CHECK_CACHE,
    COLLECTION_GAMBLING_DOMAINS,
    COLLECTION_URL_REPUTATION,
    COLLECTION_FRAUD_MESSAGES,
    COLLECTION_FEEDBACK_LOGS
)


def safe_print(message: str):
    """Print message with safe encoding handling for Windows."""
    try:
        print(message)
    except UnicodeEncodeError:
        # Fallback to ASCII encoding if UTF-8 fails
        print(message.encode('ascii', 'replace').decode('ascii'))


def now_utc() -> datetime:
    """Get current UTC time with timezone info."""
    return datetime.now(timezone.utc)


class DatabaseService:
    """Service for managing fraud detection cache in Google Cloud Firestore."""

    def __init__(self):
        """
        Initialize database service with Firestore client.
        """
        try:
            # Initialize Firestore client
            # It will automatically look for GOOGLE_APPLICATION_CREDENTIALS env var
            # or use the provided project_id if available
            
            project_id = settings.firestore_project_id
            
            # Explicitly set credentials env var if configured in settings
            # This is needed because pydantic loads it into settings object but not os.environ
            if settings.google_application_credentials and not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
                cred_path = settings.google_application_credentials
                # Resolve to absolute path if it's relative
                if not os.path.isabs(cred_path):
                    base_dir = os.getcwd() # Assuming running from project root
                    cred_path = os.path.join(base_dir, cred_path)
                
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cred_path
                safe_print(f"[CREDENTIALS] Set GOOGLE_APPLICATION_CREDENTIALS to: {cred_path}")

            # Check if using Firebase Emulator
            use_emulator = os.getenv("USE_FIREBASE_EMULATOR", "false").lower() == "true"
            
            # Get database name from environment or use project_id as database name
            database_name = os.getenv("FIRESTORE_DATABASE_ID", project_id)

            if use_emulator:
                # Use Firebase Emulator
                # Docker containers need to use host.docker.internal to access host machine
                emulator_host = os.getenv("FIRESTORE_EMULATOR_HOST", "host.docker.internal:8080")
                os.environ["FIRESTORE_EMULATOR_HOST"] = emulator_host
                self.db = firestore.Client(project=project_id, database=database_name)
                print(f"[EMULATOR] Firestore initialized with EMULATOR (Project: {self.db.project}, Database: {database_name}, HOST: {emulator_host})")
            else:
                # Use production Firestore
                self.db = firestore.Client(project=project_id, database=database_name)
                print(f"[OK] Firestore initialized successfully (Project: {self.db.project}, Database: {database_name})")

        except Exception as e:
            print(f"[ERROR] Error initializing Firestore: {e}")
            raise

    @staticmethod
    def hash_message(message: str) -> str:
        """
        Create SHA-256 hash of message for cache lookup.

        Args:
            message: Message text to hash

        Returns:
            Hex string of SHA-256 hash
        """
        # Normalize message: strip whitespace, lowercase
        normalized = message.strip().lower()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def get_cached_result(
        self, message: str, check_expiration: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached fraud detection result for a message.

        Args:
            message: Message text to look up
            check_expiration: Whether to check if cache is expired

        Returns:
            Cached result dict or None if not found/expired
        """
        message_hash = self.hash_message(message)
        
        try:
            doc_ref = self.db.collection(COLLECTION_FRAUD_CHECK_CACHE).document(message_hash)
            doc = doc_ref.get()

            if not doc.exists:
                return None

            data = doc.to_dict()
            
            # Check expiration
            if check_expiration and "expires_at" in data:
                expires_at = data["expires_at"]
                # Firestore returns datetime with timezone
                if expires_at and now_utc() > expires_at:
                    # Cache expired - delete it
                    doc_ref.delete()
                    return None

            # Update hit count and last accessed time asynchronously (fire and forget)
            # In a real high-load system, we might skip this or batch it
            try:
                doc_ref.update({
                    "hit_count": firestore.Increment(1),
                    "last_accessed_at": now_utc()
                })
            except Exception as e:
                print(f"⚠️ Failed to update cache stats: {e}")

            # Parse URL check result if exists (stored as JSON string or dict in Firestore)
            url_check_result = data.get("url_check_result")
            if isinstance(url_check_result, str):
                try:
                    url_check_result = json.loads(url_check_result)
                except json.JSONDecodeError:
                    pass

            # Build result dict
            result = {
                "category": data.get("classification"),
                "is_fraud": data.get("is_fraud"),
                "is_safe": data.get("is_safe"),
                "confidence_score": data.get("confidence_score"),
                "reason_th": data.get("reason"),
                "keywords_found": data.get("keywords_found", []),
                "message_length": len(data.get("message_text", "")),
                "url_check": url_check_result,
                "has_malicious_urls": data.get("has_malicious_urls", False),
                "model": data.get("model_used"),
                "cached": True,
                "cache_hit_count": data.get("hit_count", 0) + 1,
                "cached_at": data.get("created_at", now_utc()).isoformat(),
            }

            return result

        except Exception as e:
            print(f"❌ Firestore error getting cached result: {e}")
            return None

    def save_history(
        self,
        user_id: str,
        message: str,
        classification: str,
        is_fraud: bool,
        is_safe: bool,
        confidence_score: Optional[float] = None,
        reason: Optional[str] = None,
        url_check_result: Optional[Dict] = None,
        has_malicious_urls: bool = False,
        model_used: Optional[str] = None,
        reasoning_summary: Optional[str] = None,
        message_type: Optional[str] = None,
    ) -> Optional[str]:
        """
        Save fraud check event to history log.
        """
        if not user_id:
            return False

        try:
            from ..core.models import COLLECTION_HISTORY
            
            # Auto-detect type if not provided
            if not message_type:
                # Check if message contains URL
                import re
                url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
                if re.search(url_pattern, message):
                    message_type = "link"
                else:
                    message_type = "text"
            
            # Create new document with auto-ID
            doc_ref = self.db.collection(COLLECTION_HISTORY).document()
            
            data = {
                "user_id": user_id,
                "message_text": message,
                "type": message_type,  # Add type field
                "classification": classification,
                "is_fraud": is_fraud,
                "is_safe": is_safe,
                "confidence_score": confidence_score,
                "reason": reason,
                "reasoning_summary": reasoning_summary,
                "url_check_result": url_check_result,
                "has_malicious_urls": has_malicious_urls,
                "model_used": model_used,
                "created_at": now_utc(),
                "timestamp": now_utc() # Redundant but useful for some queries
            }
            
            doc_ref.set(data)
            return doc_ref.id

        except Exception as e:
            print(f"❌ Firestore error saving history: {e}")
            return None

    def save_feedback(
        self,
        history_id: str,
        user_id: str,
        feedback_type: str, # 'like' or 'dislike'
        comment: Optional[str] = None
    ) -> bool:
        """
        Save user feedback for a history entry.
        """
        try:
            from ..core.models import COLLECTION_FEEDBACK_LOGS
            
            doc_ref = self.db.collection(COLLECTION_FEEDBACK_LOGS).document()
            
            data = {
                "history_id": history_id,
                "user_id": user_id,
                "feedback_type": feedback_type,
                "comment": comment,
                "created_at": now_utc()
            }
            
            doc_ref.set(data)
            return True
            
        except Exception as e:
            print(f"❌ Firestore error saving feedback: {e}")
            return False

    def save_result(
        self,
        message: str,
        classification: str,
        is_fraud: bool,
        is_safe: bool,
        confidence_score: Optional[float] = None,
        reason: Optional[str] = None,
        url_check_result: Optional[Dict] = None,
        has_malicious_urls: bool = False,
        model_used: Optional[str] = None,
        cache_ttl_days: int = 30,
        user_id: Optional[str] = None,
    ) -> bool:
        """
        Save fraud detection result to cache.

        Args:
            message: Original message text
            classification: Fraud classification
            is_fraud: Whether message is fraud
            is_safe: Whether message is safe
            confidence_score: AI confidence score
            reason: Detection reason
            url_check_result: VirusTotal URL check result
            has_malicious_urls: Whether message contains malicious URLs
            model_used: AI model name
            cache_ttl_days: Cache time-to-live in days
            user_id: User ID for history tracking
        """
        message_hash = self.hash_message(message)
        
        try:
            doc_ref = self.db.collection(COLLECTION_FRAUD_CHECK_CACHE).document(message_hash)
            
            # Calculate expiration
            expires_at = now_utc() + timedelta(days=cache_ttl_days)

            # Prepare data
            # Firestore can store dicts/arrays natively, so no need to JSON dump url_check_result
            data = {
                "message_hash": message_hash,
                "message_text": message,
                "classification": classification,
                "is_fraud": is_fraud,
                "is_safe": is_safe,
                "confidence_score": confidence_score,
                "reason": reason,
                "url_check_result": url_check_result, # Store as dict directly
                "has_malicious_urls": has_malicious_urls,
                "model_used": model_used,
                "updated_at": now_utc(),
                "expires_at": expires_at,
                "user_id": user_id
            }
            
            # Use set with merge=True to update existing or create new
            # If new, we also want to set created_at and hit_count
            # But merge=True with set is tricky for "create only" fields.
            # Let's check existence first or just overwrite everything except created_at?
            # Simpler approach: just set everything. If it existed, we overwrite.
            
            # We want to preserve created_at if it exists, or set it if not.
            # And preserve hit_count.
            
            # Transactional update would be best, but for simplicity:
            doc = doc_ref.get()
            if doc.exists:
                # Update
                doc_ref.set(data, merge=True)
            else:
                # Create new
                data["created_at"] = now_utc()
                data["hit_count"] = 0
                doc_ref.set(data)

            return True

        except Exception as e:
            print(f"❌ Firestore error saving result: {e}")
            return False

    def clear_expired_cache(self) -> int:
        """
        Delete all expired cache entries.

        Returns:
            Number of entries deleted
        """
        try:
            # Query for expired documents
            query = self.db.collection(COLLECTION_FRAUD_CHECK_CACHE).where(
                filter=firestore.FieldFilter("expires_at", "<=", now_utc())
            )
            
            # Firestore doesn't support "delete all matching query", we must iterate
            # Use batches for efficiency
            batch = self.db.batch()
            count = 0
            deleted_count = 0
            
            for doc in query.stream():
                batch.delete(doc.reference)
                count += 1
                deleted_count += 1
                
                if count >= 400: # Firestore batch limit is 500
                    batch.commit()
                    batch = self.db.batch()
                    count = 0
            
            if count > 0:
                batch.commit()
                
            return deleted_count

        except Exception as e:
            print(f"❌ Firestore error clearing expired cache: {e}")
            return 0

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        Note: Counting documents in Firestore can be expensive (read costs).
        We will use aggregation queries if available or just return basic info.

        Returns:
            Dict with cache stats
        """
        try:
            # Using aggregation query for count (more efficient/cheaper than reading all docs)
            collection = self.db.collection(COLLECTION_FRAUD_CHECK_CACHE)
            count_query = collection.count()
            count_snapshot = count_query.get()
            total_entries = count_snapshot[0][0].value
            
            # For expired, we can't easily aggregate without an index on expires_at
            # Assuming index exists (will be auto-created or prompted by error)
            expired_query = collection.where(
                filter=firestore.FieldFilter("expires_at", "<=", now_utc())
            ).count()
            expired_snapshot = expired_query.get()
            expired_entries = expired_snapshot[0][0].value

            return {
                "total_entries": total_entries,
                "active_entries": total_entries - expired_entries,
                "expired_entries": expired_entries,
                "backend": "firestore"
            }

        except Exception as e:
            print(f"❌ Firestore error getting cache stats: {e}")
            return {"error": str(e)}

    def save_malicious_domain(
        self,
        domain: str,
        confidence: float = 1.0,
        category: str = "malicious_url",
        source: str = "virustotal"
    ) -> bool:
        """
        Save a malicious domain to gambling_domains blacklist.

        Args:
            domain: Domain name (e.g., 'example.com')
            confidence: Confidence score (0.0 to 1.0)
            category: Category of threat
            source: Source of detection (e.g., 'virustotal', 'user_report')

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Use domain as document ID (replace . with _ or just use as is? Firestore allows dots in IDs)
            # But to be safe and allow easy querying, let's use the domain as ID
            # Note: Firestore document IDs cannot contain forward slashes. Domains usually don't.
            
            doc_ref = self.db.collection(COLLECTION_GAMBLING_DOMAINS).document(domain)
            
            data = {
                "domain": domain,
                "confidence": confidence,
                "category": category,
                "source": source,
                "last_updated": now_utc()
            }
            
            # Check if exists to set created_at
            doc = doc_ref.get()
            if not doc.exists:
                data["created_at"] = now_utc()
                print(f"💾 Saved new malicious domain to blacklist: {domain}")
            else:
                print(f"📝 Updated malicious domain: {domain}")
                
            doc_ref.set(data, merge=True)
            return True

        except Exception as e:
            print(f"❌ Firestore error saving malicious domain: {e}")
            return False


# Singleton instance
_db_service: Optional[DatabaseService] = None


def get_database_service() -> Optional[DatabaseService]:
    """
    Get database service singleton instance.

    Returns:
        DatabaseService instance or None if initialization fails
    """
    global _db_service

    if _db_service is None:
        try:
            # Check if we have credentials
            if os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or settings.firestore_project_id:
                _db_service = DatabaseService()
            else:
                print("ℹ️ Firestore caching disabled (GOOGLE_APPLICATION_CREDENTIALS not set)")
                return None
        except Exception as e:
            print(f"⚠️ Warning: Could not initialize Firestore service: {e}")
            return None

    return _db_service
