#!/usr/bin/env python
"""
Скрипт для тестирования подключения к реальной базе 1С.

Выполняет:
1. Добавление базы 1С в систему
2. Проверку подключения (health check)
3. Чтение данных из 1С
4. Запись данных в 1С

Запуск: docker exec -it commandcenter-orchestrator-minimal python /app/test_1c_connection.py
"""

import os
import sys
import django

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.databases.models import Database
from apps.databases.odata import ODataClient
from datetime import datetime


def print_header(text):
    """Красивый заголовок."""
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80)


def print_success(text):
    """Успешное сообщение."""
    print(f"✅ {text}")


def print_error(text):
    """Сообщение об ошибке."""
    print(f"❌ {text}")


def print_info(text):
    """Информационное сообщение."""
    print(f"ℹ️  {text}")


def add_database():
    """Добавить базу 1С в систему."""
    print_header("Шаг 1: Добавление базы 1С в систему")

    # Данные подключения
    db_config = {
        'id': 'test-dev-db',
        'name': 'Test DEV Database',
        'description': 'Тестовая база 1С для разработки',
        'host': 'host.docker.internal',  # Для доступа к localhost с внутри Docker
        'port': 80,
        'base_name': 'dev',
        'odata_url': 'http://host.docker.internal/dev/odata/standard.odata',
        'username': 'Delans-Admin',
        'password': '',  # Пустой пароль
        'status': Database.STATUS_ACTIVE,
        'health_check_enabled': True,
    }

    # Проверяем существует ли база
    existing_db = Database.objects.filter(id=db_config['id']).first()
    if existing_db:
        print_info(f"База '{db_config['name']}' уже существует. Обновляю данные...")
        for key, value in db_config.items():
            setattr(existing_db, key, value)
        existing_db.save()
        db = existing_db
    else:
        print_info(f"Создаю новую базу '{db_config['name']}'...")
        db = Database.objects.create(**db_config)

    print_success(f"База добавлена: {db.name} (ID: {db.id})")
    print_info(f"  OData URL: {db.odata_url}")
    print_info(f"  Пользователь: {db.username}")
    print_info(f"  Пароль: {'(пустой)' if not db.password else '***'}")

    return db


def test_connection(db: Database):
    """Проверить подключение к базе 1С."""
    print_header("Шаг 2: Проверка подключения к базе 1С")

    try:
        client = ODataClient(
            base_url=db.odata_url,
            username=db.username,
            password=db.password
        )

        print_info("Пытаюсь подключиться к OData endpoint...")

        # Получить метаданные (это проверит подключение)
        metadata_url = f"{db.odata_url}/$metadata"
        print_info(f"  URL метаданных: {metadata_url}")

        response = client.session.get(metadata_url, timeout=10)

        if response.status_code == 200:
            print_success("Подключение успешно!")
            print_info(f"  Статус код: {response.status_code}")
            print_info(f"  Размер ответа: {len(response.content)} байт")

            # Обновить health check в БД
            db.mark_health_check(success=True, response_time=response.elapsed.total_seconds() * 1000)

            client.close()
            return True
        else:
            print_error(f"Ошибка подключения! Статус код: {response.status_code}")
            db.mark_health_check(success=False)
            client.close()
            return False

    except Exception as e:
        print_error(f"Ошибка при подключении: {e}")
        db.mark_health_check(success=False, error_message=str(e))
        return False


def test_read_data(db: Database):
    """Протестировать чтение данных из 1С."""
    print_header("Шаг 3: Чтение данных из базы 1С")

    try:
        client = ODataClient(
            base_url=db.odata_url,
            username=db.username,
            password=db.password
        )

        # Попробуем получить список справочников
        print_info("Получаю список доступных справочников...")

        # Самый базовый запрос - получить первые 5 записей любого справочника
        # Обычно есть справочник Организации или Контрагенты
        test_entities = [
            'Catalog_Организации',
            'Catalog_Контрагенты',
            'Catalog_Номенклатура',
            'Catalog_Пользователи',
        ]

        success = False
        for entity in test_entities:
            try:
                print_info(f"  Пробую читать: {entity}...")
                url = f"{db.odata_url}/{entity}?$top=5"
                response = client.session.get(url, timeout=10)

                if response.status_code == 200:
                    data = response.json()
                    count = len(data.get('value', []))
                    print_success(f"    Успешно! Прочитано {count} записей из {entity}")

                    if count > 0:
                        print_info("    Пример первой записи:")
                        first_record = data['value'][0]
                        for key, value in list(first_record.items())[:5]:  # Первые 5 полей
                            print_info(f"      {key}: {value}")

                    success = True
                    break

            except Exception as e:
                print_info(f"    Не найдено или ошибка: {e}")
                continue

        client.close()

        if success:
            print_success("Чтение данных работает!")
            return True
        else:
            print_error("Не удалось прочитать данные ни из одного справочника")
            print_info("  Возможно, нужно уточнить названия справочников в вашей базе")
            return False

    except Exception as e:
        print_error(f"Ошибка при чтении данных: {e}")
        return False


def test_write_data(db: Database):
    """Протестировать запись данных в 1С."""
    print_header("Шаг 4: Запись данных в базу 1С")

    print_info("⚠️  ВНИМАНИЕ: Запись данных в production базу может быть опасна!")
    print_info("  Убедитесь что это тестовая база!")

    try:
        client = ODataClient(
            base_url=db.odata_url,
            username=db.username,
            password=db.password
        )

        # Попробуем создать тестовую запись в простом справочнике
        # Обычно можно создать запись в справочнике Пользователи или Организации

        test_name = f"TEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        test_entities = [
            ('Catalog_Пользователи', {'Наименование': test_name, 'Код': test_name[:9]}),
            ('Catalog_Контрагенты', {'Наименование': test_name}),
            ('Catalog_Организации', {'Наименование': test_name}),
        ]

        success = False
        for entity, data in test_entities:
            try:
                print_info(f"  Пробую создать запись в: {entity}...")
                url = f"{db.odata_url}/{entity}"

                response = client.session.post(
                    url,
                    json=data,
                    headers={'Content-Type': 'application/json'},
                    timeout=15
                )

                if response.status_code in [200, 201]:
                    created = response.json()
                    print_success("    Запись создана успешно!")
                    print_info(f"    ID: {created.get('Ref_Key', 'N/A')}")
                    print_info(f"    Наименование: {created.get('Наименование', 'N/A')}")
                    success = True
                    break
                else:
                    print_info(f"    Ошибка {response.status_code}: {response.text[:200]}")

            except Exception as e:
                print_info(f"    Не удалось: {e}")
                continue

        client.close()

        if success:
            print_success("Запись данных работает!")
            print_info("  ⚠️  Не забудьте удалить тестовые записи из базы 1С!")
            return True
        else:
            print_error("Не удалось записать данные")
            print_info("  Возможные причины:")
            print_info("    - У пользователя нет прав на запись")
            print_info("    - Неправильные обязательные поля")
            print_info("    - Названия справочников не совпадают")
            return False

    except Exception as e:
        print_error(f"Ошибка при записи данных: {e}")
        return False


def main():
    """Главная функция."""
    print_header("🚀 Тест подключения к базе 1С")
    print_info(f"Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        # Шаг 1: Добавить базу
        db = add_database()

        # Шаг 2: Проверить подключение
        connection_ok = test_connection(db)
        if not connection_ok:
            print_error("\n❌ Подключение не удалось. Остальные тесты пропущены.")
            print_info("\nВозможные проблемы:")
            print_info("  1. База 1С не запущена")
            print_info("  2. Неправильный URL (проверьте http://localhost/dev/odata/standard.odata)")
            print_info("  3. Неправильные credentials")
            print_info("  4. Публикация OData не настроена в 1С")
            sys.exit(1)

        # Шаг 3: Чтение данных
        read_ok = test_read_data(db)

        # Шаг 4: Запись данных
        write_ok = test_write_data(db)

        # Итог
        print_header("📊 Итоги тестирования")
        print_info(f"  Подключение: {'✅ OK' if connection_ok else '❌ FAILED'}")
        print_info(f"  Чтение:      {'✅ OK' if read_ok else '❌ FAILED'}")
        print_info(f"  Запись:      {'✅ OK' if write_ok else '❌ FAILED'}")

        if connection_ok and read_ok:
            print_success("\n🎉 Тестирование завершено успешно!")
            print_info("  Теперь вы можете использовать CommandCenter1C для работы с этой базой.")
        else:
            print_error("\n⚠️  Некоторые тесты не прошли. Проверьте логи выше.")

    except Exception as e:
        print_error(f"\n💥 Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
