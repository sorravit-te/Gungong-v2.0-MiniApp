#!/usr/bin/env python3
"""
Test Firestore Connection
ทดสอบการเชื่อมต่อ Firestore และ Service Account
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from google.cloud import firestore
    from google.auth import default
    import google.auth.exceptions
except ImportError:
    print("❌ Error: Required packages not installed")
    print("Please install: pip install google-cloud-firestore google-auth")
    sys.exit(1)


def print_success(msg):
    print(f"✅ {msg}")


def print_error(msg):
    print(f"❌ {msg}")


def print_info(msg):
    print(f"ℹ️  {msg}")


def print_warning(msg):
    print(f"⚠️  {msg}")


def test_environment():
    """Test environment variables"""
    print("\n" + "="*50)
    print("Testing Environment Variables")
    print("="*50)

    # Check GOOGLE_APPLICATION_CREDENTIALS
    creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if not creds_path:
        print_error("GOOGLE_APPLICATION_CREDENTIALS not set")
        return False

    print_info(f"Credentials path: {creds_path}")

    if not os.path.exists(creds_path):
        print_error(f"Credentials file not found: {creds_path}")
        return False

    print_success("Credentials file exists")

    # Check FIRESTORE_PROJECT_ID
    project_id = os.getenv('FIRESTORE_PROJECT_ID')
    if not project_id:
        print_error("FIRESTORE_PROJECT_ID not set")
        return False

    print_info(f"Project ID: {project_id}")
    print_success("Environment variables OK")

    return True


def test_authentication():
    """Test Google Cloud authentication"""
    print("\n" + "="*50)
    print("Testing Authentication")
    print("="*50)

    try:
        credentials, project = default()
        print_success(f"Authenticated with project: {project}")
        return True
    except google.auth.exceptions.DefaultCredentialsError as e:
        print_error(f"Authentication failed: {e}")
        return False
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        return False


def test_firestore_connection():
    """Test Firestore connection"""
    print("\n" + "="*50)
    print("Testing Firestore Connection")
    print("="*50)

    project_id = os.getenv('FIRESTORE_PROJECT_ID')

    try:
        # Initialize Firestore client
        db = firestore.Client(project=project_id)
        print_success("Firestore client initialized")

        return db
    except Exception as e:
        print_error(f"Failed to initialize Firestore: {e}")
        return None


def test_firestore_write(db):
    """Test Firestore write operation"""
    print("\n" + "="*50)
    print("Testing Firestore Write")
    print("="*50)

    try:
        # Create test document
        test_data = {
            'test': 'connection_test',
            'timestamp': datetime.now(),
            'message': 'This is a test document'
        }

        doc_ref = db.collection('_test').document('connection_test')
        doc_ref.set(test_data)

        print_success("Write operation successful")
        return True
    except Exception as e:
        print_error(f"Write operation failed: {e}")
        return False


def test_firestore_read(db):
    """Test Firestore read operation"""
    print("\n" + "="*50)
    print("Testing Firestore Read")
    print("="*50)

    try:
        doc_ref = db.collection('_test').document('connection_test')
        doc = doc_ref.get()

        if doc.exists:
            print_success("Read operation successful")
            print_info(f"Document data: {doc.to_dict()}")
            return True
        else:
            print_error("Document not found")
            return False
    except Exception as e:
        print_error(f"Read operation failed: {e}")
        return False


def test_firestore_delete(db):
    """Test Firestore delete operation"""
    print("\n" + "="*50)
    print("Testing Firestore Delete")
    print("="*50)

    try:
        doc_ref = db.collection('_test').document('connection_test')
        doc_ref.delete()

        print_success("Delete operation successful")
        return True
    except Exception as e:
        print_error(f"Delete operation failed: {e}")
        return False


def test_collections(db):
    """List existing collections"""
    print("\n" + "="*50)
    print("Listing Collections")
    print("="*50)

    try:
        collections = db.collections()
        collection_names = [col.id for col in collections]

        if collection_names:
            print_success(f"Found {len(collection_names)} collections:")
            for name in collection_names:
                print(f"  - {name}")
        else:
            print_info("No collections found (database is empty)")

        return True
    except Exception as e:
        print_error(f"Failed to list collections: {e}")
        return False


def main():
    """Main test function"""
    print("\n" + "="*50)
    print("GunGong Firestore Connection Test")
    print("="*50)

    # Load .env if exists
    try:
        from dotenv import load_dotenv
        if os.path.exists('.env'):
            load_dotenv()
            print_success("Loaded .env file")
        else:
            print_warning(".env file not found")
    except ImportError:
        print_warning("python-dotenv not installed, skipping .env loading")

    results = []

    # Test 1: Environment
    results.append(("Environment Variables", test_environment()))

    # Test 2: Authentication
    results.append(("Authentication", test_authentication()))

    # Test 3: Firestore Connection
    db = test_firestore_connection()
    results.append(("Firestore Connection", db is not None))

    if db:
        # Test 4: Write
        results.append(("Firestore Write", test_firestore_write(db)))

        # Test 5: Read
        results.append(("Firestore Read", test_firestore_read(db)))

        # Test 6: Delete
        results.append(("Firestore Delete", test_firestore_delete(db)))

        # Test 7: List Collections
        results.append(("List Collections", test_collections(db)))

    # Summary
    print("\n" + "="*50)
    print("Test Summary")
    print("="*50)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print("\n" + "="*50)
    print(f"Results: {passed}/{total} tests passed")
    print("="*50)

    if passed == total:
        print_success("All tests passed! Firestore is working correctly.")
        return 0
    else:
        print_error(f"{total - passed} test(s) failed. Please check configuration.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
