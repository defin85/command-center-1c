#!/usr/bin/env python
"""Тест чтения справочника Патенты."""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.databases.odata import ODataClient
import json

def test_patents():
    """Прочитать справочник Патенты."""

    client = ODataClient(
        base_url="http://host.docker.internal/dev/odata/standard.odata",
        username="Delans-Admin",
        password=""
    )

    print("=" * 80)
    print("Чтение справочника Catalog_Патенты")
    print("=" * 80)

    try:
        # Получить все записи
        url = f"{client.base_url}/Catalog_Патенты?$top=10"
        print(f"\nЗапрос: {url}")

        response = client.session.get(url, timeout=10)

        print(f"\nСтатус: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            records = data.get('value', [])

            print(f"✅ Успешно! Получено записей: {len(records)}")

            if records:
                print("\n" + "=" * 80)
                print("Первая запись:")
                print("=" * 80)
                first = records[0]
                for key, value in first.items():
                    print(f"  {key}: {value}")

                print("\n" + "=" * 80)
                print("Все записи (кратко):")
                print("=" * 80)
                for i, record in enumerate(records, 1):
                    ref_key = record.get('Ref_Key', 'N/A')
                    desc = record.get('Description', 'N/A')
                    code = record.get('Code', 'N/A')
                    print(f"  {i}. [{code}] {desc} (ID: {ref_key})")
            else:
                print("ℹ️  Справочник пустой (нет записей)")

        else:
            print(f"❌ Ошибка: {response.status_code}")
            print(f"Ответ: {response.text[:500]}")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()

if __name__ == '__main__':
    test_patents()
