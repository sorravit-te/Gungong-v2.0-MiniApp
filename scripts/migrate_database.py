"""Database migration script for new performance optimization tables.

This script creates the new tables needed for performance optimization:
- gambling_domains: Domain blacklist for instant detection
- url_reputation_cache: Cache VirusTotal + Gambling results
- fraud_messages: Unique fraud messages for similarity analysis (deduplicated)

Usage:
    python -m scripts.migrate_database
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backend.core.models import Base, GamblingDomain, URLReputationCache, FraudMessage
from src.backend.services.database_service import get_database_service
from sqlalchemy import inspect


def check_table_exists(engine, table_name: str) -> bool:
    """Check if a table exists in the database.

    Args:
        engine: SQLAlchemy engine
        table_name: Name of table to check

    Returns:
        True if table exists, False otherwise
    """
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def migrate_database():
    """Create new performance optimization tables."""

    print("🔧 Starting database migration...")
    print("="*60)

    db_service = get_database_service()
    if not db_service:
        print("❌ Database not configured (DATABASE_URL not set)")
        return False

    engine = db_service.engine

    try:
        # Check which tables already exist
        print("\n📊 Checking existing tables...")
        tables_to_create = [
            ("gambling_domains", GamblingDomain),
            ("url_reputation_cache", URLReputationCache),
            ("fraud_messages", FraudMessage),
        ]

        tables_exist = {}
        for table_name, model_class in tables_to_create:
            exists = check_table_exists(engine, table_name)
            tables_exist[table_name] = exists
            status = "✅ EXISTS" if exists else "❌ MISSING"
            print(f"   {status}: {table_name}")

        # Create missing tables
        print("\n🔨 Creating missing tables...")
        created_count = 0

        for table_name, model_class in tables_to_create:
            if not tables_exist[table_name]:
                print(f"\n   Creating table: {table_name}")
                try:
                    # Create single table
                    model_class.__table__.create(engine, checkfirst=True)
                    print(f"   ✅ Created: {table_name}")
                    created_count += 1

                    # Show table schema
                    inspector = inspect(engine)
                    columns = inspector.get_columns(table_name)
                    print(f"      Columns:")
                    for col in columns:
                        nullable = "NULL" if col['nullable'] else "NOT NULL"
                        print(f"         - {col['name']}: {col['type']} {nullable}")

                except Exception as e:
                    print(f"   ❌ Failed to create {table_name}: {e}")
            else:
                print(f"   ⏭️  Skipped: {table_name} (already exists)")

        # Summary
        print("\n" + "="*60)
        print(f"📊 Migration Summary:")
        print(f"   ✅ Tables created: {created_count}")
        print(f"   ⏭️  Tables skipped: {len(tables_to_create) - created_count}")

        if created_count > 0:
            print(f"\n✅ Database migration completed successfully!")
            print(f"\n💡 Next steps:")
            print(f"   1. Run: python -m scripts.populate_gambling_domains")
            print(f"   2. Restart the bot to use the new tables")
        else:
            print(f"\n✅ All tables already exist, no migration needed!")

        return True

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def show_table_info():
    """Show information about all fraud detection tables."""

    print("📊 Database Table Information")
    print("="*60)

    db_service = get_database_service()
    if not db_service:
        print("❌ Database not configured (DATABASE_URL not set)")
        return

    engine = db_service.engine
    session = db_service.get_session()

    try:
        # Tables to check
        tables = [
            ("fraud_check_cache", "Message classification cache"),
            ("gambling_domains", "Gambling domain blacklist"),
            ("url_reputation_cache", "URL reputation cache (VirusTotal + Gambling)"),
            ("fraud_messages", "Unique fraud messages (deduplicated)"),
        ]

        for table_name, description in tables:
            exists = check_table_exists(engine, table_name)

            if exists:
                # Count rows
                if table_name == "fraud_check_cache":
                    from src.backend.core.models import FraudCheckCache
                    count = session.query(FraudCheckCache).count()
                elif table_name == "gambling_domains":
                    count = session.query(GamblingDomain).count()
                elif table_name == "url_reputation_cache":
                    count = session.query(URLReputationCache).count()
                elif table_name == "fraud_messages":
                    count = session.query(FraudMessage).count()
                else:
                    count = "N/A"

                print(f"\n✅ {table_name}")
                print(f"   Description: {description}")
                print(f"   Row count: {count}")

                # Show schema
                inspector = inspect(engine)
                columns = inspector.get_columns(table_name)
                print(f"   Columns: {len(columns)}")
                for col in columns[:5]:  # Show first 5 columns
                    nullable = "NULL" if col['nullable'] else "NOT NULL"
                    print(f"      - {col['name']}: {col['type']} {nullable}")
                if len(columns) > 5:
                    print(f"      ... and {len(columns) - 5} more")
            else:
                print(f"\n❌ {table_name}")
                print(f"   Description: {description}")
                print(f"   Status: NOT CREATED")

    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        session.close()

    print("\n" + "="*60)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Database migration for performance optimization")
    parser.add_argument(
        "--info",
        action="store_true",
        help="Show table information instead of migrating"
    )

    args = parser.parse_args()

    if args.info:
        # Show table info
        show_table_info()
    else:
        # Run migration
        success = migrate_database()

        if success:
            print("\n" + "="*60)
            print("📊 Current Database Status:")
            print("="*60)
            show_table_info()
