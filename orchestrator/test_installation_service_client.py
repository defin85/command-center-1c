#!/usr/bin/env python
"""
Тест для проверки InstallationServiceClient.

Тестирует связь Django → installation-service
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
os.environ.setdefault('INSTALLATION_SERVICE_URL', 'http://localhost:8086')

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

django.setup()

# Now import Django modules
from apps.databases.clients import InstallationServiceClient

def test_health_check():
    """Test 1: Health check installation-service"""
    print("=" * 60)
    print("TEST 1: Health Check installation-service")
    print("=" * 60)

    try:
        with InstallationServiceClient() as client:
            print(f"URL: {client.base_url}")
            print(f"Timeout: {client.timeout}s")
            print()

            print("Checking health...")
            is_healthy = client.health_check()

            if is_healthy:
                print("[OK] installation-service is HEALTHY")
                return True
            else:
                print("[FAIL] installation-service is UNAVAILABLE")
                return False

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print()
    print("Testing Django -> installation-service integration")
    print()

    success = test_health_check()

    print()
    print("=" * 60)
    if success:
        print("ALL TESTS PASSED")
    else:
        print("TESTS FAILED")
    print("=" * 60)
    print()

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
