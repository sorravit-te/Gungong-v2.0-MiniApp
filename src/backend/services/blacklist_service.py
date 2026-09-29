from typing import Dict, Optional, List
from datetime import datetime, timezone
from .database_service import DatabaseService, get_database_service
from ..core.models import COLLECTION_BLACKLIST_BANK_ACCOUNTS, COLLECTION_BLACKLIST_PHONE_NUMBERS

def now_utc() -> datetime:
    """Get current UTC time with timezone info."""
    return datetime.now(timezone.utc)

class BlacklistService:
    """Service for managing blacklist data (bank accounts, phone numbers)."""

    def __init__(self, db_service: DatabaseService):
        """Initialize blacklist service."""
        if not isinstance(db_service, DatabaseService):
            raise TypeError("db_service must be an instance of DatabaseService")
        self.db_service = db_service
        self.db = db_service.db

    def check_bank_account(self, bank_code: str, account_number: str) -> Dict:
        """
        Check if a bank account is blacklisted.
        Returns details if found, else None.
        """
        try:
            # Query by account number (primary key)
            # Note: In a real system, we might query by bank_code + account_number
            # But for simplicity, we assume account_number is unique enough or we check both.
            
            # Normalize account number (remove dashes/spaces)
            clean_acc_num = "".join(filter(str.isdigit, account_number))
            
            docs = self.db.collection(COLLECTION_BLACKLIST_BANK_ACCOUNTS)\
                .where("account_number", "==", clean_acc_num)\
                .stream()

            for doc in docs:
                data = doc.to_dict()
                # Optional: Check bank code if provided
                if bank_code and data.get("bank_code") != bank_code:
                    continue
                    
                return {
                    "is_blacklisted": True,
                    "details": data
                }

            return {"is_blacklisted": False}

        except Exception as e:
            print(f"❌ Error checking bank account: {e}")
            return {"is_blacklisted": False, "error": str(e)}

    def check_phone_number(self, phone_number: str) -> Dict:
        """
        Check if a phone number is blacklisted.
        Returns details if found, else None.
        """
        try:
            # Normalize phone number (remove dashes/spaces, handle +66)
            clean_phone = "".join(filter(str.isdigit, phone_number))
            if clean_phone.startswith("66"):
                clean_phone = "0" + clean_phone[2:]
            
            doc_ref = self.db.collection(COLLECTION_BLACKLIST_PHONE_NUMBERS).document(clean_phone)
            doc = doc_ref.get()

            if doc.exists:
                return {
                    "is_blacklisted": True,
                    "details": doc.to_dict()
                }

            return {"is_blacklisted": False}

        except Exception as e:
            print(f"❌ Error checking phone number: {e}")
            return {"is_blacklisted": False, "error": str(e)}

    def seed_mock_data(self):
        """
        Seed mock data for testing.
        """
        print("🌱 Seeding mock blacklist data...")
        
        # 1. Mock Bank Accounts (Mule Accounts)
        mock_accounts = [
            {
                "account_number": "1234567890",
                "bank_code": "KBANK",
                "account_name": "นายสมชาย ขายของโกง",
                "report_count": 15,
                "risk_level": "High",
                "category": "Mule Account (บัญชีม้า)",
                "last_reported": now_utc()
            },
            {
                "account_number": "9876543210",
                "bank_code": "SCB",
                "account_name": "นางสาวสมหญิง หลอกโอน",
                "report_count": 8,
                "risk_level": "Medium",
                "category": "Fraudulent Seller",
                "last_reported": now_utc()
            },
             {
                "account_number": "1112223334",
                "bank_code": "BBL",
                "account_name": "นายมิจฉา ชีพ",
                "report_count": 50,
                "risk_level": "Critical",
                "category": "Money Laundering",
                "last_reported": now_utc()
            }
        ]

        for acc in mock_accounts:
            try:
                self.db.collection(COLLECTION_BLACKLIST_BANK_ACCOUNTS).document(acc["account_number"]).set(acc)
                print(f"   - Added account: {acc['account_number']}")
            except Exception as e:
                print(f"   - Failed to add account {acc['account_number']}: {e}")

        # 2. Mock Phone Numbers (Call Center / SMS Spam)
        mock_phones = [
            {
                "phone_number": "0812345678",
                "owner_name": "แก๊งคอลเซ็นเตอร์ (อ้างเป็นตำรวจ)",
                "report_count": 120,
                "risk_level": "Critical",
                "category": "Call Center Gang",
                "last_reported": now_utc()
            },
            {
                "phone_number": "0909998888",
                "owner_name": "SMS เงินกู้เถื่อน",
                "report_count": 45,
                "risk_level": "High",
                "category": "SMS Spam",
                "last_reported": now_utc()
            },
            {
                 "phone_number": "021111111",
                 "owner_name": "ขายประกัน (รบกวน)",
                 "report_count": 10,
                 "risk_level": "Low",
                 "category": "Nuisance Call",
                 "last_reported": now_utc()
            }
        ]

        for phone in mock_phones:
            try:
                self.db.collection(COLLECTION_BLACKLIST_PHONE_NUMBERS).document(phone["phone_number"]).set(phone)
                print(f"   - Added phone: {phone['phone_number']}")
            except Exception as e:
                print(f"   - Failed to add phone {phone['phone_number']}: {e}")
        
        print("✅ Mock data seeding completed.")

# Singleton instance
_blacklist_service_instance = None

def get_blacklist_service() -> Optional[BlacklistService]:
    """Get singleton instance of BlacklistService."""
    global _blacklist_service_instance
    if _blacklist_service_instance is None:
        try:
            db_service = get_database_service()
            if db_service:
                _blacklist_service_instance = BlacklistService(db_service)
        except Exception as e:
            print(f"⚠️ Failed to initialize BlacklistService: {e}")
            return None
    return _blacklist_service_instance
