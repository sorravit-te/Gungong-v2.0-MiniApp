"""
Fraud Message Service - Smart deduplication for fraud messages using Firestore.

Only saves unique fraud messages (>70% similarity threshold).
Used for similarity analysis to avoid false positives from safe messages.
"""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from google.cloud import firestore

from ..core.models import COLLECTION_FRAUD_MESSAGES
from ..core.performance_config import get_performance_config
from .database_service import DatabaseService


def now_utc() -> datetime:
    """Get current UTC time with timezone info."""
    return datetime.now(timezone.utc)


class FraudMessageService:
    """
    Service for managing unique fraud messages with deduplication in Firestore.
    """

    def __init__(self, db_service: DatabaseService):
        """
        Initialize fraud message service.

        Args:
            db_service: A valid, initialized DatabaseService instance.
        """
        if not db_service:
            raise ValueError("DatabaseService instance is required.")
        self.db_service = db_service
        self.db = db_service.db  # Access Firestore client directly
        self.config = get_performance_config()

        # Similarity threshold from config
        self.similarity_threshold = self.config.FRAUD_MESSAGE_SIMILARITY_THRESHOLD

        # Cache for TF-IDF (reload periodically)
        self._tfidf_cache: Optional[Dict] = None
        self._cache_loaded_at: Optional[datetime] = None
        self._cache_ttl = timedelta(hours=1)  # Reload every hour

    @staticmethod
    def hash_message(message: str) -> str:
        """Create SHA-256 hash of message."""
        normalized = message.strip().lower()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def save_fraud_message(
        self,
        message_text: str,
        category: str,
        confidence_score: Optional[float] = None,
        keywords: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Save fraud message with smart deduplication.
        """
        try:
            # Step 1: Check for similar existing messages
            # Note: For Firestore, we might need to fetch all fraud messages to check similarity
            # This could be expensive if there are many. 
            # Optimization: Only fetch recent ones or use LSH (Locality Sensitive Hashing) in future.
            # For now, we fetch all (assuming < 1000 messages).
            
            similar = self._find_similar_message(message_text)

            if similar and similar["similarity"] > self.similarity_threshold:
                # Duplicate found - update hit_count
                doc_ref = self.db.collection(COLLECTION_FRAUD_MESSAGES).document(similar["id"])
                
                doc_ref.update({
                    "hit_count": firestore.Increment(1),
                    "last_seen_at": now_utc()
                })

                print(f"📊 Fraud message similar to existing ({similar['similarity']:.0%}), updated hit count")

                return {
                    "saved": False,
                    "message_id": similar["id"],
                    "similarity": similar["similarity"],
                    "action": "updated",
                    "hit_count": -1 # Unknown without reading back
                }

            # Step 2: No similar message - insert new
            message_hash = self.hash_message(message_text)
            
            # Use hash as document ID for deduplication by exact match
            doc_ref = self.db.collection(COLLECTION_FRAUD_MESSAGES).document(message_hash)
            
            data = {
                "message_hash": message_hash,
                "message_text": message_text,
                "category": category,
                "confidence_score": confidence_score,
                "keywords": keywords,
                "hit_count": 1,
                "created_at": now_utc(),
                "last_seen_at": now_utc()
            }

            doc_ref.set(data)

            # Invalidate cache
            self._tfidf_cache = None

            print(f"💾 New unique fraud message saved (id={message_hash})")

            return {
                "saved": True,
                "message_id": message_hash,
                "similarity": 0.0,
                "action": "inserted",
                "hit_count": 1
            }

        except Exception as e:
            print(f"❌ Error saving fraud message: {e}")
            return {
                "saved": False,
                "message_id": None,
                "similarity": 0.0,
                "action": "error",
                "error": str(e)
            }

    def _find_similar_message(
        self,
        message_text: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find most similar existing fraud message.
        """
        try:
            # Fetch all fraud messages (limit to 1000 for performance)
            docs = self.db.collection(COLLECTION_FRAUD_MESSAGES).limit(1000).stream()
            
            messages = []
            ids = []
            for doc in docs:
                data = doc.to_dict()
                if "message_text" in data:
                    messages.append(data["message_text"])
                    ids.append(doc.id)
            
            if not messages:
                return None

            # Tokenization with pythainlp (if available)
            try:
                from pythainlp.tokenize import word_tokenize
                def tokenize_thai(text):
                    return " ".join(word_tokenize(text, engine="newmm"))
                
                message_tokenized = tokenize_thai(message_text)
                existing_tokenized = [tokenize_thai(t) for t in messages]
            except ImportError:
                message_tokenized = message_text
                existing_tokenized = messages

            # TF-IDF similarity
            vectorizer = TfidfVectorizer(
                analyzer='char',
                ngram_range=(2, 4),
                max_features=1000
            )

            all_texts = [message_tokenized] + existing_tokenized
            tfidf_matrix = vectorizer.fit_transform(all_texts)

            # Compute similarity
            query_vector = tfidf_matrix[0:1]
            doc_vectors = tfidf_matrix[1:]

            similarities = cosine_similarity(query_vector, doc_vectors)[0]

            # Find maximum
            max_idx = np.argmax(similarities)
            max_similarity = similarities[max_idx]

            if max_similarity > 0.3:  # At least 30% similar
                return {
                    "id": ids[max_idx],
                    "message_text": messages[max_idx],
                    "similarity": float(max_similarity)
                }

        except Exception as e:
            print(f"⚠️  Similarity check failed: {e}")

        return None

    def get_all_fraud_messages(self) -> List[Dict]:
        """Get all fraud messages for similarity analysis."""
        try:
            docs = self.db.collection(COLLECTION_FRAUD_MESSAGES).stream()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            print(f"❌ Error getting all fraud messages: {e}")
            return []

    def get_fraud_count(self) -> int:
        """Get total count of unique fraud messages."""
        try:
            # Use aggregation query
            query = self.db.collection(COLLECTION_FRAUD_MESSAGES).count()
            snapshot = query.get()
            return snapshot[0][0].value
        except Exception as e:
            print(f"❌ Error getting fraud count: {e}")
            return 0

    def clear_old_messages(self, days: int = 90) -> int:
        """Clear fraud messages older than specified days."""
        try:
            cutoff = now_utc() - timedelta(days=days)
            
            query = self.db.collection(COLLECTION_FRAUD_MESSAGES).where(
                filter=firestore.FieldFilter("created_at", "<", cutoff)
            )
            
            batch = self.db.batch()
            count = 0
            deleted_count = 0
            
            for doc in query.stream():
                batch.delete(doc.reference)
                count += 1
                deleted_count += 1
                if count >= 400:
                    batch.commit()
                    batch = self.db.batch()
                    count = 0
            
            if count > 0:
                batch.commit()

            print(f"🗑️  Deleted {deleted_count} old fraud messages")
            return deleted_count

        except Exception as e:
            print(f"❌ Error clearing old messages: {e}")
            return 0


# Singleton instance
_fraud_message_service_instance: Optional[FraudMessageService] = None


def get_fraud_message_service() -> Optional[FraudMessageService]:
    """Get or create singleton fraud message service instance."""
    global _fraud_message_service_instance
    if _fraud_message_service_instance is None:
        from .database_service import get_database_service
        db_service = get_database_service()
        if db_service:
            _fraud_message_service_instance = FraudMessageService(db_service)
        else:
            print("ℹ️ Fraud Message service disabled (DATABASE_URL not configured)")
            return None
    return _fraud_message_service_instance
