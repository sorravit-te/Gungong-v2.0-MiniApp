"""Import fraud/spam messages from text files into fraud_messages table.

This script reads fraud messages from text files and imports them into the database
for similarity analysis and pattern learning.

Usage:
    python -m scripts.import_fraud_dataset
"""

import sys
from pathlib import Path
import re

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backend.services.fraud_message_service import get_fraud_message_service


def clean_message(text: str) -> str:
    """Clean and normalize message text.

    Args:
        text: Raw message text

    Returns:
        Cleaned message text
    """
    # Remove leading numbers (e.g., "1. ", "2. ")
    text = re.sub(r'^\d+\.\s*', '', text)

    # Remove separator lines
    text = re.sub(r'^-{4,}$', '', text, flags=re.MULTILINE)

    # Remove empty lines
    text = '\n'.join(line for line in text.split('\n') if line.strip())

    # Strip whitespace
    text = text.strip()

    return text


def parse_scamming_fraud_file(file_path: str) -> list:
    """Parse scamming_fraud_text.txt file.

    Messages are separated by blank lines or numbers.

    Args:
        file_path: Path to scamming_fraud_text.txt

    Returns:
        List of fraud messages
    """
    messages = []

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split by double newlines or numbered items
    parts = re.split(r'\n\s*\n+|\n(?=\d+\.)', content)

    for part in parts:
        cleaned = clean_message(part)
        if cleaned and len(cleaned) > 10:  # Minimum length
            messages.append(cleaned)

    return messages


def parse_spam_dataset_file(file_path: str) -> list:
    """Parse spam_dataset_500.txt file.

    Messages are separated by "--------------------"

    Args:
        file_path: Path to spam_dataset_500.txt

    Returns:
        List of spam messages
    """
    messages = []

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split by separator
    parts = content.split('--------------------')

    for part in parts:
        cleaned = clean_message(part)
        if cleaned and len(cleaned) > 10:  # Minimum length
            messages.append(cleaned)

    return messages


def import_messages(messages: list, category: str = "FRAUD_GAMBLING_AD") -> dict:
    """Import messages into fraud_messages table.

    Args:
        messages: List of fraud messages
        category: Category (FRAUD_GAMBLING_AD or SCAM_MALICIOUS)

    Returns:
        Import statistics
    """
    fraud_service = get_fraud_message_service()
    if not fraud_service:
        print("❌ Fraud message service not available")
        return {"error": "Service not available"}

    stats = {
        "total": len(messages),
        "inserted": 0,
        "updated": 0,
        "skipped": 0,
        "errors": 0
    }

    print(f"\n📥 Importing {len(messages)} messages...")
    print(f"   Category: {category}")
    print(f"   Deduplication: 70% similarity threshold")
    print()

    for i, message in enumerate(messages, 1):
        try:
            # Save with deduplication
            result = fraud_service.save_fraud_message(
                message_text=message,
                category=category,
                confidence_score=0.95,  # High confidence from dataset
                keywords=[]
            )

            if result["saved"]:
                stats["inserted"] += 1
                if i % 10 == 0 or i <= 5:  # Show first 5 and every 10th
                    print(f"   ✅ [{i}/{len(messages)}] Inserted: {message[:60]}...")
            else:
                stats["updated"] += 1
                similarity = result.get("similarity", 0)
                if i <= 5:  # Show first 5 updates
                    print(f"   ✏️  [{i}/{len(messages)}] Updated (similar {similarity:.0%}): {message[:60]}...")

        except Exception as e:
            stats["errors"] += 1
            print(f"   ❌ [{i}/{len(messages)}] Error: {e}")

    return stats


def main():
    """Main import function."""
    print("🎓 Fraud Dataset Importer")
    print("=" * 80)

    # File paths
    base_path = Path(__file__).parent.parent / "tests"
    scamming_file = base_path / "scamming_fraud_text.txt"
    spam_file = base_path / "spam_dataset_500.txt"

    all_stats = {
        "total_files": 0,
        "total_messages": 0,
        "total_inserted": 0,
        "total_updated": 0,
        "total_errors": 0
    }

    # Import scamming_fraud_text.txt
    if scamming_file.exists():
        print(f"\n📂 File 1: {scamming_file.name}")
        print("-" * 80)

        messages = parse_scamming_fraud_file(str(scamming_file))
        print(f"   Parsed: {len(messages)} messages")

        stats = import_messages(messages, category="FRAUD_GAMBLING_AD")

        all_stats["total_files"] += 1
        all_stats["total_messages"] += stats["total"]
        all_stats["total_inserted"] += stats["inserted"]
        all_stats["total_updated"] += stats["updated"]
        all_stats["total_errors"] += stats["errors"]

        print(f"\n   📊 Results:")
        print(f"      ✅ Inserted: {stats['inserted']}")
        print(f"      ✏️  Updated: {stats['updated']}")
        print(f"      ❌ Errors: {stats['errors']}")
    else:
        print(f"⚠️  File not found: {scamming_file}")

    # Import spam_dataset_500.txt
    if spam_file.exists():
        print(f"\n📂 File 2: {spam_file.name}")
        print("-" * 80)

        messages = parse_spam_dataset_file(str(spam_file))
        print(f"   Parsed: {len(messages)} messages")

        stats = import_messages(messages, category="SCAM_MALICIOUS")

        all_stats["total_files"] += 1
        all_stats["total_messages"] += stats["total"]
        all_stats["total_inserted"] += stats["inserted"]
        all_stats["total_updated"] += stats["updated"]
        all_stats["total_errors"] += stats["errors"]

        print(f"\n   📊 Results:")
        print(f"      ✅ Inserted: {stats['inserted']}")
        print(f"      ✏️  Updated: {stats['updated']}")
        print(f"      ❌ Errors: {stats['errors']}")
    else:
        print(f"⚠️  File not found: {spam_file}")

    # Final summary
    print(f"\n{'=' * 80}")
    print(f"📊 FINAL SUMMARY")
    print(f"{'=' * 80}")
    print(f"   Files processed: {all_stats['total_files']}")
    print(f"   Total messages: {all_stats['total_messages']}")
    print(f"   ✅ Inserted (unique): {all_stats['total_inserted']}")
    print(f"   ✏️  Updated (duplicates): {all_stats['total_updated']}")
    print(f"   ❌ Errors: {all_stats['total_errors']}")

    # Show deduplication rate
    if all_stats['total_messages'] > 0:
        unique_rate = (all_stats['total_inserted'] / all_stats['total_messages']) * 100
        print(f"\n   📈 Deduplication:")
        print(f"      Unique messages: {unique_rate:.1f}%")
        print(f"      Duplicates removed: {100 - unique_rate:.1f}%")

    print(f"\n✅ Import completed!")
    print(f"\n💡 Next steps:")
    print(f"   1. Restart bot: docker-compose restart gungong-bot")
    print(f"   2. Bot will now use these {all_stats['total_inserted']} unique fraud messages")
    print(f"   3. Similarity analysis will be more accurate")


if __name__ == "__main__":
    main()
