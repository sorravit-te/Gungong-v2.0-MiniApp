"""Similarity service for comparing messages using TF-IDF with Firestore."""

from typing import List, Dict, Any, Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from datetime import datetime, timezone, timedelta
import time

from .database_service import get_database_service
from .fraud_message_service import get_fraud_message_service


class SimilarityService:
    """Service for calculating message similarity using TF-IDF."""

    def __init__(self):
        """Initialize similarity service."""
        self.vectorizer = None
        self.fraud_messages = []
        self.fraud_vectors = None
        self.last_loaded_time = None  # Timestamp of last cache load
        self.cache_ttl = 3600  # Cache Time-To-Live: 1 hour (in seconds)

    def tokenize_thai(self, text: str) -> str:
        """
        Tokenize Thai text for TF-IDF.
        """
        try:
            from pythainlp.tokenize import word_tokenize
            tokens = word_tokenize(text, engine="newmm")
            return " ".join(tokens)
        except ImportError:
            return text

    def load_fraud_messages_from_db(self) -> int:
        """
        Load fraud messages from FraudMessage collection (deduplicated, FRAUD only).
        Uses in-memory cache with 1-hour TTL to avoid reloading on every request.
        """
        # Check if cache is still fresh (within TTL)
        if self.fraud_messages and self.last_loaded_time:
            time_since_load = time.time() - self.last_loaded_time
            if time_since_load < self.cache_ttl:
                return len(self.fraud_messages)

        fraud_service = get_fraud_message_service()
        if not fraud_service:
            return 0

        try:
            # Get all fraud messages from Firestore
            # Note: In a real production app with millions of messages, 
            # we would not load all into memory. We would use a vector database.
            # For this scale, loading all (or top 1000) is fine.
            fraud_entries = fraud_service.get_all_fraud_messages()

            self.fraud_messages = [
                {
                    "text": entry.get("message_text"),
                    "category": entry.get("category"),
                    "hit_count": entry.get("hit_count", 1),
                    "confidence": entry.get("confidence_score"),
                }
                for entry in fraud_entries
                if entry.get("message_text")
            ]

            # Create TF-IDF vectors
            if self.fraud_messages:
                texts = [self.tokenize_thai(msg["text"]) for msg in self.fraud_messages]
                self.vectorizer = TfidfVectorizer()
                self.fraud_vectors = self.vectorizer.fit_transform(texts)

            # Update cache timestamp
            self.last_loaded_time = time.time()
            print(f"✅ Loaded {len(self.fraud_messages)} fraud messages into TF-IDF cache")

            return len(self.fraud_messages)

        except Exception as e:
            print(f"❌ Error loading fraud messages: {e}")
            return 0

    def calculate_danger_score(self, message: str) -> Dict[str, Any]:
        """
        Calculate danger score by comparing with fraud messages in database.
        """
        # Load fraud messages if not loaded
        if not self.fraud_messages:
            count = self.load_fraud_messages_from_db()
            if count == 0:
                return {
                    "danger_percentage": 0.0,
                    "most_similar_message": None,
                    "similarity_score": 0.0,
                    "total_fraud_messages": 0,
                    "similar_messages": [],
                }

        try:
            # Tokenize input message
            tokenized = self.tokenize_thai(message)

            # Transform to TF-IDF vector
            if self.vectorizer:
                message_vector = self.vectorizer.transform([tokenized])

                # Calculate cosine similarity with all fraud messages
                similarities = cosine_similarity(message_vector, self.fraud_vectors)[0]

                # Get top 5 most similar messages
                top_indices = np.argsort(similarities)[-5:][::-1]
                similar_messages = [
                    {
                        "message": self.fraud_messages[idx]["text"][:100] + "..."
                        if len(self.fraud_messages[idx]["text"]) > 100
                        else self.fraud_messages[idx]["text"],
                        "classification": self.fraud_messages[idx]["category"],
                        "similarity": float(similarities[idx]),
                        "hit_count": self.fraud_messages[idx]["hit_count"],
                    }
                    for idx in top_indices
                    if similarities[idx] > 0.1  # Only include if similarity > 10%
                ]

                # Get highest similarity
                max_similarity = float(np.max(similarities))
                max_idx = int(np.argmax(similarities))

                # Calculate danger percentage (0-100%)
                danger_percentage = max_similarity * 100

                return {
                    "danger_percentage": round(danger_percentage, 2),
                    "most_similar_message": self.fraud_messages[max_idx]["text"]
                    if max_similarity > 0.1
                    else None,
                    "similarity_score": round(max_similarity, 4),
                    "total_fraud_messages": len(self.fraud_messages),
                    "similar_messages": similar_messages,
                }
            else:
                 return {
                    "danger_percentage": 0.0,
                    "most_similar_message": None,
                    "similarity_score": 0.0,
                    "total_fraud_messages": 0,
                    "similar_messages": [],
                }

        except Exception as e:
            print(f"❌ Error calculating danger score: {e}")
            return {
                "danger_percentage": 0.0,
                "most_similar_message": None,
                "similarity_score": 0.0,
                "total_fraud_messages": len(self.fraud_messages),
                "similar_messages": [],
                "error": str(e),
            }

    def get_message_analysis(self, message: str) -> Dict[str, Any]:
        """
        Get complete message analysis (frequency + danger score) in single operation.
        """
        # Load fraud messages once (uses cache if available)
        if not self.fraud_messages:
            self.load_fraud_messages_from_db()

        # Get both analyses using same loaded data
        frequency = self.check_message_frequency(message)
        danger_analysis = self.calculate_danger_score(message)

        return {
            "frequency": frequency,
            "danger_analysis": danger_analysis
        }

    def check_message_frequency(self, message: str) -> Dict[str, Any]:
        """
        Check how many times this exact message was seen before.
        """
        db_service = get_database_service()
        if not db_service:
            return {
                "seen_before": False,
                "times_seen": 0,
                "message": "Database not configured",
            }

        # Check if message exists in cache
        cached = db_service.get_cached_result(message, check_expiration=False)

        if cached:
            return {
                "seen_before": True,
                "times_seen": cached.get("hit_count", 0) + 1,  # +1 for current check
                "first_seen": cached.get("created_at"),
                "last_seen": cached.get("last_accessed_at"),
                "classification": cached.get("classification"),
                "is_fraud": cached.get("is_fraud"),
            }
        else:
            return {
                "seen_before": False,
                "times_seen": 1,  # First time seeing this
                "message": "This is the first time seeing this message",
            }


# Singleton instance
_similarity_service: Optional[SimilarityService] = None


def get_similarity_service() -> Optional[SimilarityService]:
    """
    Get similarity service singleton instance.
    """
    global _similarity_service

    if _similarity_service is None:
        db_service = get_database_service()
        if db_service:
            _similarity_service = SimilarityService()
        else:
            print("ℹ️ Similarity service disabled (DATABASE_URL not configured)")
            return None

    return _similarity_service
