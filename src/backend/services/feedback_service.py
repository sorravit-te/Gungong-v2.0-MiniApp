"""Service for handling user feedback with Firestore."""

from urllib.parse import parse_qs
from datetime import datetime, timezone
from google.cloud import firestore
from .database_service import DatabaseService, get_database_service
from .fraud_message_service import get_fraud_message_service
from ..core.models import (
    COLLECTION_FEEDBACK_LOGS, 
    COLLECTION_FRAUD_CHECK_CACHE,
    COLLECTION_FRAUD_MESSAGES
)


def now_utc() -> datetime:
    """Get current UTC time with timezone info."""
    return datetime.now(timezone.utc)


class FeedbackService:
    """Service for processing and storing user feedback using Firestore."""

    def __init__(self, db_service: DatabaseService):
        """Initialize the feedback service."""
        if not isinstance(db_service, DatabaseService):
            raise TypeError("db_service must be an instance of DatabaseService")
        self.db_service = db_service
        self.db = db_service.db

    def save_feedback_from_postback(self, postback_data: str, user_id: str) -> bool:
        """
        Parses postback data, saves feedback, and corrects data if needed.

        Args:
            postback_data: The query string from the LINE postback action.
                           e.g., "action=feedback&feedback=correct_fraud&hash=..."
            user_id: The LINE user ID of the user who provided feedback.

        Returns:
            True if feedback was saved successfully, False otherwise.
        """
        try:
            parsed_data = parse_qs(postback_data)
            
            action = parsed_data.get("action", [None])[0]
            feedback_value = parsed_data.get("feedback", [None])[0]
            message_hash = parsed_data.get("hash", [None])[0]

            if action != "feedback" or not feedback_value or not message_hash:
                print(f"⚠️ Invalid postback data received: {postback_data}")
                return False

            # 1. Get original message context
            doc_ref = self.db.collection(COLLECTION_FRAUD_CHECK_CACHE).document(message_hash)
            doc = doc_ref.get()
            
            original_text = None
            original_classification = None
            
            if doc.exists:
                data = doc.to_dict()
                original_text = data.get("message_text")
                original_classification = data.get("classification")
            else:
                print(f"⚠️ Original message not found for hash: {message_hash}")

            # 2. Save feedback log
            feedback_data = {
                "message_hash": message_hash,
                "message_text": original_text,
                "original_classification": original_classification,
                "user_feedback": feedback_value,
                "user_id": user_id,
                "notes": "Feedback from postback button.",
                "created_at": now_utc()
            }
            self.db.collection(COLLECTION_FEEDBACK_LOGS).add(feedback_data)
            print(f"💾 Feedback saved: User '{user_id}' rated message (hash: {message_hash[:8]}...) as '{feedback_value}'")

            # 3. Apply corrections based on feedback
            if original_text:
                self._apply_correction(message_hash, original_text, feedback_value)
            
            return True

        except Exception as e:
            print(f"❌ ERROR saving feedback: {e}")
            return False

    def _apply_correction(self, message_hash: str, message_text: str, feedback_value: str):
        """
        Apply data corrections based on feedback.
        """
        try:
            fraud_service = get_fraud_message_service()
            cache_ref = self.db.collection(COLLECTION_FRAUD_CHECK_CACHE).document(message_hash)

            # Case A: False Positive (AI said Fraud, User says Safe)
            if feedback_value == "incorrect_fraud":
                print(f"🔄 Correcting False Positive for {message_hash[:8]}...")
                
                # 1. Update Cache to Safe
                # IMPORTANT: Must also clear URL threats, otherwise LineService will override to HIGH risk
                cache_ref.update({
                    "classification": "SAFE",
                    "is_fraud": False,
                    "is_safe": True,
                    "confidence_score": 0.0,
                    "reason": "User reported as safe (False Positive correction)",
                    "updated_at": now_utc(),
                    "has_malicious_urls": False,
                    "url_check.is_dangerous": False,
                    "url_threat_detected": False
                })
                
                # 2. Remove from Fraud Messages collection
                # Note: FraudMessageService uses hash as ID
                self.db.collection(COLLECTION_FRAUD_MESSAGES).document(message_hash).delete()
                print("✅ Removed from fraud_messages and updated cache to SAFE")

                # 3. Remove domains from blacklist (True Learning)
                try:
                    # Get original url_check data from doc (before update)
                    if doc.exists:
                        data = doc.to_dict()
                        url_check = data.get("url_check", {})
                        if url_check:
                            from .gambling_domain_service import get_gambling_domain_service
                            gambling_service = get_gambling_domain_service()
                            
                            if gambling_service:
                                # Collect all domains to remove
                                domains_to_remove = set()
                                
                                # From malicious_urls
                                for url in url_check.get("malicious_urls", []):
                                    from urllib.parse import urlparse
                                    try:
                                        parsed = urlparse(url)
                                        domain = parsed.netloc or parsed.path.split('/')[0]
                                        if domain:
                                            domains_to_remove.add(domain)
                                    except:
                                        pass

                                # From gambling_urls
                                for url in url_check.get("gambling_urls", []):
                                    from urllib.parse import urlparse
                                    try:
                                        parsed = urlparse(url)
                                        domain = parsed.netloc or parsed.path.split('/')[0]
                                        if domain:
                                            domains_to_remove.add(domain)
                                    except:
                                        pass
                                
                                # Remove each domain from blacklist AND add to whitelist
                                for domain in domains_to_remove:
                                    gambling_service.remove_domain(domain)
                                    gambling_service.add_whitelist_domain(domain, reason="user_feedback_safe")
                                    print(f"✅ Removed {domain} from blacklist and added to whitelist")

                except Exception as e:
                    print(f"⚠️ Error removing domains from blacklist: {e}")

            # Case B: False Negative (AI said Safe, User says Fraud)
            elif feedback_value == "incorrect_safe":
                print(f"🔄 Correcting False Negative for {message_hash[:8]}...")
                
                # 1. Update Cache to Fraud
                cache_ref.update({
                    "classification": "FRAUD_USER_REPORT",
                    "is_fraud": True,
                    "is_safe": False,
                    "confidence_score": 100.0,
                    "reason": "User reported as fraud (False Negative correction)",
                    "updated_at": now_utc()
                })
                
                # 2. Add to Fraud Messages collection
                if fraud_service:
                    fraud_service.save_fraud_message(
                        message_text=message_text,
                        category="FRAUD_USER_REPORT",
                        confidence_score=100.0,
                        keywords=["user_reported"]
                    )
                print("✅ Added to fraud_messages and updated cache to FRAUD")

            # Case C: Confirmed Fraud (Reinforce)
            elif feedback_value == "correct_fraud":
                # Optional: Increase confidence or hit count?
                # For now, just ensure it's in the fraud list if it was missing for some reason
                if fraud_service:
                    # This will just update hit count if exists
                    fraud_service.save_fraud_message(
                        message_text=message_text,
                        category="FRAUD_CONFIRMED",
                        confidence_score=100.0
                    )

        except Exception as e:
            print(f"❌ Error applying correction: {e}")


# Singleton instance
_feedback_service_instance = None


def get_feedback_service() -> "FeedbackService":
    """Get or create singleton FeedbackService instance."""
    global _feedback_service_instance
    if _feedback_service_instance is None:
        db_service = get_database_service()
        if not db_service:
            print("ℹ️ Feedback service disabled (DATABASE_URL not configured)")
            return None
        _feedback_service_instance = FeedbackService(db_service)
    return _feedback_service_instance
