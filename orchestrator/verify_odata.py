#!/usr/bin/env python
"""
Quick verification script для OData client.

Проверяет что все модули импортируются без ошибок.
"""

import sys
import os

# Добавить orchestrator в path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    print("=" * 60)
    print("OData Client Verification")
    print("=" * 60)

    try:
        # Test imports
        print("\n1. Testing imports...")
        from apps.databases.odata import (
            ODataClient,
            ODataSessionManager,
            session_manager,
            ODataError,
            ODataConnectionError,
            ODataAuthenticationError,
            ODataRequestError,
            OData1CSpecificError,
            ODataTimeoutError,
        )
        print("   ✅ All imports successful")

        # Test entities module
        print("\n2. Testing entities module...")
        from apps.databases.odata.entities import (
            ENTITY_TYPES,
            COMMON_CATALOGS,
            COMMON_DOCUMENTS,
            get_entity_url_part,
            parse_entity_url_part,
        )
        print("   ✅ Entities module imported")

        # Test entity URL building
        print("\n3. Testing entity URL functions...")
        url_part = get_entity_url_part('Catalog', 'Пользователи')
        assert url_part == 'Catalog_Пользователи', f"Expected 'Catalog_Пользователи', got '{url_part}'"
        print(f"   ✅ get_entity_url_part: {url_part}")

        parsed = parse_entity_url_part('Catalog_Пользователи')
        assert parsed == {'entity_type': 'Catalog', 'entity_name': 'Пользователи'}
        print(f"   ✅ parse_entity_url_part: {parsed}")

        # Test SessionManager singleton
        print("\n4. Testing SessionManager singleton...")
        manager1 = ODataSessionManager()
        manager2 = ODataSessionManager()
        assert manager1 is manager2, "SessionManager is not a singleton!"
        print("   ✅ SessionManager is singleton")

        # Test SessionManager global instance
        print("\n5. Testing global session_manager...")
        assert session_manager is manager1, "Global session_manager is different instance!"
        print("   ✅ Global session_manager is same instance")

        # Test SessionManager stats
        stats = session_manager.get_stats()
        assert 'active_clients' in stats
        assert 'total_created' in stats
        print(f"   ✅ SessionManager stats: {stats}")

        # Test ODataClient initialization (without actual connection)
        print("\n6. Testing ODataClient initialization...")
        try:
            client = ODataClient(
                base_url="http://localhost/test/odata/standard.odata",
                username="test",
                password="test"
            )
            print("   ✅ ODataClient initialized")

            # Test URL building
            url = client._build_entity_url("Catalog_Пользователи")
            assert url == "http://localhost/test/odata/standard.odata/Catalog_Пользователи"
            print(f"   ✅ URL building works: {url}")

            # Clean up
            client.close()
            print("   ✅ Client closed successfully")

        except Exception as e:
            print(f"   ❌ Error initializing client: {e}")
            return False

        # Test exceptions
        print("\n7. Testing exception hierarchy...")
        try:
            raise ODataConnectionError("Test error")
        except ODataError:
            print("   ✅ Exception hierarchy works")
        except Exception:
            print("   ❌ Exception hierarchy broken")
            return False

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        print("\nOData client ready to use!")
        print("\nNext steps:")
        print("- Install requirements: pip install -r requirements.txt")
        print("- Run unit tests: pytest apps/databases/tests/")
        print("- Integrate with Django models (Day 3)")

        return True

    except ImportError as e:
        print(f"\n❌ Import Error: {e}")
        print("\nMake sure you have installed all dependencies:")
        print("  pip install -r requirements.txt")
        return False

    except Exception as e:
        print(f"\n❌ Unexpected Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
