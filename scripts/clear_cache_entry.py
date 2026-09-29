import argparse
import os
import sys
import hashlib

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, text
from src.backend.core.config import settings
from src.backend.core.models import FraudCheckCache

def hash_message(message: str) -> str:
    """
    Create SHA-256 hash of a message.
    (This must be identical to the one in DatabaseService)
    """
    normalized = message.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

def clear_cache_entry(message_to_clear: str):
    """
    Connects to the database and deletes a specific cache entry.
    """
    if not settings.database_url:
        print("❌ DATABASE_URL is not configured. Cannot connect to the database.")
        sys.exit(1)

    print(f"Connecting to database...")
    try:
        engine = create_engine(settings.database_url)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = SessionLocal()
        print("✅ Connection successful.")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        sys.exit(1)

    try:
        # 1. Calculate the hash of the message to be cleared
        message_hash = hash_message(message_to_clear)
        print(f"💬 Message to clear: '{message_to_clear}'")
        print(f"🔑 Calculated Hash: {message_hash}")

        # 2. Find the cache entry
        entry_to_delete = session.query(FraudCheckCache).filter(FraudCheckCache.message_hash == message_hash).first()

        if not entry_to_delete:
            print("🟢 No matching cache entry found. Nothing to delete.")
            return

        # 3. Delete the entry
        print(f"🗑️ Found matching entry (ID: {entry_to_delete.id}, Created: {entry_to_delete.created_at}). Deleting...")
        session.delete(entry_to_delete)
        session.commit()
        print("✅ Successfully deleted the cache entry.")

    except Exception as e:
        print(f"❌ An error occurred during deletion: {e}")
        session.rollback()
    finally:
        session.close()
        print("🔒 Database connection closed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Clear a specific fraud detection cache entry from the database by providing the message string."
    )
    parser.add_argument(
        "message",
        type=str,
        help="The exact message string of the cache entry you want to delete."
    )
    args = parser.parse_args()

    clear_cache_entry(args.message)
