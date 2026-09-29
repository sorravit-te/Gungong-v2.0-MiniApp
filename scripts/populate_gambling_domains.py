"""Script to populate gambling_domains table with known gambling sites.

This script adds a comprehensive list of gambling domains to the database
for instant fraud detection without needing AI or VirusTotal checks.

Usage:
    python -m scripts.populate_gambling_domains
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backend.services.database_service import get_database_service
from src.backend.core.models import GamblingDomain
from sqlalchemy.exc import IntegrityError


# Comprehensive list of known gambling domains (Thai + International)
GAMBLING_DOMAINS = [
    # Thai Gambling Sites (Most Common)
    {"domain": "ufabet.com", "category": "sports_betting", "confidence": 1.0, "source": "manual"},
    {"domain": "sbobet.com", "category": "sports_betting", "confidence": 1.0, "source": "manual"},
    {"domain": "fun88.com", "category": "sports_betting", "confidence": 1.0, "source": "manual"},
    {"domain": "w88.com", "category": "sports_betting", "confidence": 1.0, "source": "manual"},
    {"domain": "maxbet.com", "category": "sports_betting", "confidence": 1.0, "source": "manual"},
    {"domain": "188bet.com", "category": "sports_betting", "confidence": 1.0, "source": "manual"},
    {"domain": "dafabet.com", "category": "sports_betting", "confidence": 1.0, "source": "manual"},
    {"domain": "m88.com", "category": "sports_betting", "confidence": 1.0, "source": "manual"},
    {"domain": "12bet.com", "category": "sports_betting", "confidence": 1.0, "source": "manual"},
    {"domain": "happyluke.com", "category": "sports_betting", "confidence": 1.0, "source": "manual"},

    # Thai Online Casinos
    {"domain": "joker123.net", "category": "casino", "confidence": 1.0, "source": "manual"},
    {"domain": "slotxo.com", "category": "casino", "confidence": 1.0, "source": "manual"},
    {"domain": "pgslot.com", "category": "casino", "confidence": 1.0, "source": "manual"},
    {"domain": "sa-gaming.com", "category": "casino", "confidence": 1.0, "source": "manual"},
    {"domain": "sexybaccarat.com", "category": "casino", "confidence": 1.0, "source": "manual"},
    {"domain": "allbet.com", "category": "casino", "confidence": 1.0, "source": "manual"},
    {"domain": "ae-casino.com", "category": "casino", "confidence": 1.0, "source": "manual"},
    {"domain": "918kiss.com", "category": "casino", "confidence": 1.0, "source": "manual"},

    # Thai Lottery & Number Games
    {"domain": "lottovip.com", "category": "lottery", "confidence": 1.0, "source": "manual"},
    {"domain": "huay.com", "category": "lottery", "confidence": 1.0, "source": "manual"},
    {"domain": "ruay.com", "category": "lottery", "confidence": 1.0, "source": "manual"},
    {"domain": "jetsadabet.com", "category": "lottery", "confidence": 1.0, "source": "manual"},

    # International Gambling Sites (Popular in Thailand)
    {"domain": "bet365.com", "category": "sports_betting", "confidence": 1.0, "source": "manual"},
    {"domain": "ladbrokes.com", "category": "sports_betting", "confidence": 1.0, "source": "manual"},
    {"domain": "williamhill.com", "category": "sports_betting", "confidence": 1.0, "source": "manual"},
    {"domain": "betway.com", "category": "sports_betting", "confidence": 1.0, "source": "manual"},
    {"domain": "10bet.com", "category": "sports_betting", "confidence": 1.0, "source": "manual"},

    # International Online Casinos
    {"domain": "888casino.com", "category": "casino", "confidence": 1.0, "source": "manual"},
    {"domain": "betfair.com", "category": "casino", "confidence": 1.0, "source": "manual"},
    {"domain": "pokerstars.com", "category": "poker", "confidence": 1.0, "source": "manual"},
    {"domain": "partypoker.com", "category": "poker", "confidence": 1.0, "source": "manual"},

    # Crypto Gambling Sites
    {"domain": "stake.com", "category": "casino", "confidence": 0.95, "source": "manual"},
    {"domain": "bc.game", "category": "casino", "confidence": 0.95, "source": "manual"},
    {"domain": "rollbit.com", "category": "casino", "confidence": 0.95, "source": "manual"},

    # Common Variations & Phishing Domains (Lower Confidence)
    {"domain": "ufabet168.com", "category": "sports_betting", "confidence": 0.9, "source": "manual"},
    {"domain": "ufabet777.com", "category": "sports_betting", "confidence": 0.9, "source": "manual"},
    {"domain": "ufabet888.com", "category": "sports_betting", "confidence": 0.9, "source": "manual"},
    {"domain": "sbo-bet.com", "category": "sports_betting", "confidence": 0.9, "source": "manual"},
    {"domain": "sbobetasia.com", "category": "sports_betting", "confidence": 0.9, "source": "manual"},

    # Add more as needed...
]


def populate_gambling_domains():
    """Populate gambling_domains table with known gambling sites."""

    print("🎲 Starting gambling domains population...")

    db_service = get_database_service()
    if not db_service:
        print("❌ Database not configured (DATABASE_URL not set)")
        return False

    session = db_service.get_session()

    try:
        inserted_count = 0
        skipped_count = 0
        updated_count = 0

        for domain_data in GAMBLING_DOMAINS:
            try:
                # Check if domain already exists
                existing = session.query(GamblingDomain).filter_by(
                    domain=domain_data["domain"]
                ).first()

                if existing:
                    # Update if confidence or category changed
                    if (existing.confidence != domain_data["confidence"] or
                        existing.category != domain_data["category"]):
                        existing.confidence = domain_data["confidence"]
                        existing.category = domain_data["category"]
                        existing.source = domain_data["source"]
                        updated_count += 1
                        print(f"   ✏️  Updated: {domain_data['domain']} ({domain_data['category']})")
                    else:
                        skipped_count += 1
                        print(f"   ⏭️  Skipped: {domain_data['domain']} (already exists)")
                else:
                    # Insert new domain
                    gambling_domain = GamblingDomain(
                        domain=domain_data["domain"],
                        category=domain_data["category"],
                        confidence=domain_data["confidence"],
                        source=domain_data["source"]
                    )
                    session.add(gambling_domain)
                    inserted_count += 1
                    print(f"   ✅ Inserted: {domain_data['domain']} ({domain_data['category']}, confidence: {domain_data['confidence']:.0%})")

            except IntegrityError as e:
                print(f"   ⚠️  Integrity error for {domain_data['domain']}: {e}")
                session.rollback()
                continue

        # Commit all changes
        session.commit()

        print(f"\n📊 Summary:")
        print(f"   ✅ Inserted: {inserted_count}")
        print(f"   ✏️  Updated: {updated_count}")
        print(f"   ⏭️  Skipped: {skipped_count}")
        print(f"   📝 Total domains in list: {len(GAMBLING_DOMAINS)}")

        # Count total in database
        total_in_db = session.query(GamblingDomain).count()
        print(f"   💾 Total domains in database: {total_in_db}")

        print(f"\n✅ Gambling domains population completed!")
        return True

    except Exception as e:
        print(f"\n❌ Error populating gambling domains: {e}")
        session.rollback()
        return False
    finally:
        session.close()


def test_domain_lookup(domain: str):
    """Test if a domain is in the blacklist.

    Args:
        domain: Domain to check (e.g., "ufabet.com")
    """
    print(f"\n🔍 Testing domain lookup: {domain}")

    db_service = get_database_service()
    if not db_service:
        print("❌ Database not configured")
        return

    session = db_service.get_session()

    try:
        result = session.query(GamblingDomain).filter_by(domain=domain).first()

        if result:
            print(f"✅ Found in blacklist:")
            print(f"   Domain: {result.domain}")
            print(f"   Category: {result.category}")
            print(f"   Confidence: {result.confidence:.0%}")
            print(f"   Source: {result.source}")
            print(f"   Added: {result.created_at}")
        else:
            print(f"❌ Not found in blacklist")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        session.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Populate gambling domains database")
    parser.add_argument(
        "--test",
        type=str,
        help="Test domain lookup (e.g., --test ufabet.com)",
        metavar="DOMAIN"
    )

    args = parser.parse_args()

    if args.test:
        # Test domain lookup
        test_domain_lookup(args.test)
    else:
        # Populate database
        success = populate_gambling_domains()

        if success:
            # Test a few domains
            print("\n" + "="*60)
            print("🧪 Testing domain lookups...")
            print("="*60)
            test_domain_lookup("ufabet.com")
            test_domain_lookup("sbobet.com")
            test_domain_lookup("google.com")  # Should NOT be found
