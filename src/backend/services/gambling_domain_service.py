"""
Gambling Domain Service

Manages gambling_domains collection for auto-detected gambling websites using Firestore.
"""

from typing import Dict, List, Optional
from datetime import datetime, timezone
from .database_service import DatabaseService, get_database_service
from ..core.models import COLLECTION_GAMBLING_DOMAINS, COLLECTION_WHITELISTED_DOMAINS


def now_utc() -> datetime:
    """Get current UTC time with timezone info."""
    return datetime.now(timezone.utc)


class GamblingDomainService:
    """Service for managing gambling domains using Firestore."""

    def __init__(self, db_service: DatabaseService):
        """Initialize gambling domain service."""
        if not isinstance(db_service, DatabaseService):
            raise TypeError("db_service must be an instance of DatabaseService")
        self.db_service = db_service
        self.db = db_service.db

    def add_whitelist_domain(self, domain: str, reason: str = "manual_feedback") -> bool:
        """
        Add a domain to the whitelist.
        """
        try:
            doc_ref = self.db.collection(COLLECTION_WHITELISTED_DOMAINS).document(domain)
            data = {
                "domain": domain,
                "reason": reason,
                "created_at": now_utc(),
                "last_updated": now_utc()
            }
            doc_ref.set(data)
            print(f"✅ Whitelisted domain: {domain}")
            return True
        except Exception as e:
            print(f"❌ Error whitelisting domain {domain}: {e}")
            return False

    def is_whitelisted(self, domain: str) -> bool:
        """
        Check if a domain is whitelisted.
        """
        try:
            doc_ref = self.db.collection(COLLECTION_WHITELISTED_DOMAINS).document(domain)
            doc = doc_ref.get()
            return doc.exists
        except Exception as e:
            print(f"❌ Error checking whitelist for {domain}: {e}")
            return False


    def add_or_update_domain(
        self,
        domain: str,
        confidence: float,
        category: str = "gambling",
        source: str = "auto_detected",
        keywords: Optional[List[str]] = None
    ) -> Dict:
        """
        Add new gambling domain or update existing one.
        """
        try:
            # Use domain as document ID
            doc_ref = self.db.collection(COLLECTION_GAMBLING_DOMAINS).document(domain)
            doc = doc_ref.get()

            if doc.exists:
                # Update existing domain
                data = doc.to_dict()
                old_confidence = data.get("confidence", 0.0)
                
                # Average the confidence scores
                new_confidence = (old_confidence + confidence) / 2

                update_data = {
                    "confidence": new_confidence,
                    "last_updated": now_utc()
                }

                # Update category if source is more reliable
                if source in ["manual", "virustotal"]:
                    update_data["category"] = category
                    update_data["source"] = source

                doc_ref.update(update_data)

                print(
                    f"💾 Updated gambling domain: {domain} "
                    f"(confidence: {old_confidence:.0%} → {new_confidence:.0%})"
                )

                return {
                    "saved": True,
                    "domain": domain,
                    "confidence": new_confidence,
                    "was_new": False
                }

            else:
                # Insert new domain
                new_domain_data = {
                    "domain": domain,
                    "confidence": confidence,
                    "category": category,
                    "source": source,
                    "keywords": keywords,
                    "created_at": now_utc(),
                    "last_updated": now_utc()
                }

                doc_ref.set(new_domain_data)

                print(
                    f"💾 Saved new gambling domain: {domain} "
                    f"(confidence: {confidence:.0%}, source: {source})"
                )

                return {
                    "saved": True,
                    "domain": domain,
                    "confidence": confidence,
                    "was_new": True
                }

        except Exception as e:
            print(f"❌ Error saving gambling domain {domain}: {e}")
            return {
                "saved": False,
                "domain": domain,
                "confidence": 0.0,
                "was_new": False,
                "error": str(e)
            }

    def is_gambling_domain(self, domain: str, min_confidence: float = 0.5) -> bool:
        """
        Check if domain is a known gambling domain.
        """
        try:
            doc_ref = self.db.collection(COLLECTION_GAMBLING_DOMAINS).document(domain)
            doc = doc_ref.get()

            if doc.exists:
                data = doc.to_dict()
                if data.get("confidence", 0.0) >= min_confidence:
                    return True

            return False

        except Exception as e:
            print(f"❌ Error checking gambling domain {domain}: {e}")
            return False

    def get_domain_info(self, domain: str) -> Optional[Dict]:
        """
        Get information about a gambling domain.
        """
        try:
            doc_ref = self.db.collection(COLLECTION_GAMBLING_DOMAINS).document(domain)
            doc = doc_ref.get()

            if doc.exists:
                return doc.to_dict()

            return None

        except Exception as e:
            print(f"❌ Error getting gambling domain info {domain}: {e}")
            return None

    def get_all_domains(self, min_confidence: float = 0.5) -> List[str]:
        """
        Get all gambling domains with confidence >= threshold.
        """
        try:
            # Use query with filter
            query = self.db.collection(COLLECTION_GAMBLING_DOMAINS).where(
                filter=firestore.FieldFilter("confidence", ">=", min_confidence)
            )
            
            domains = []
            for doc in query.stream():
                data = doc.to_dict()
                if "domain" in data:
                    domains.append(data["domain"])
            
            return domains

        except Exception as e:
            print(f"❌ Error getting all gambling domains: {e}")
            return []


    def remove_domain(self, domain: str) -> bool:
        """
        Remove a domain from the gambling blacklist (whitelist it).
        """
        try:
            doc_ref = self.db.collection(COLLECTION_GAMBLING_DOMAINS).document(domain)
            doc_ref.delete()
            print(f"🗑️ Removed domain from blacklist: {domain}")
            return True
        except Exception as e:
            print(f"❌ Error removing domain {domain}: {e}")
            return False


# Singleton instance
_gambling_domain_service_instance = None


def get_gambling_domain_service() -> Optional[GamblingDomainService]:
    """Get or create singleton gambling domain service instance."""
    global _gambling_domain_service_instance
    if _gambling_domain_service_instance is None:
        db_service = get_database_service()
        if db_service:
            _gambling_domain_service_instance = GamblingDomainService(db_service)
        else:
            print("ℹ️ Gambling Domain service disabled (DATABASE_URL not configured)")
            return None
    return _gambling_domain_service_instance
