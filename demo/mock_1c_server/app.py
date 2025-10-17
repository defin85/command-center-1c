"""
Mock 1C OData Server для тестирования CommandCenter1C

Реализует OData v3 API с 1С-специфичным форматом URL.
Поддерживает базовые CRUD операции для тестирования.
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import uuid
import os
from datetime import datetime
from functools import wraps

app = Flask(__name__)
CORS(app)

# Configuration
ODATA_USERNAME = os.getenv('ODATA_USERNAME', 'Администратор')
ODATA_PASSWORD = os.getenv('ODATA_PASSWORD', 'mock_password')
DB_NAME = os.getenv('DB_NAME', 'test_db')
PORT = int(os.getenv('PORT', 8080))

# In-memory storage
databases = {
    'Catalog_Пользователи': {},
    'Catalog_Организации': {},
    'Catalog_Номенклатура': {}
}

# Entity schemas
ENTITY_SCHEMAS = {
    'Catalog_Пользователи': {
        'required': ['Description', 'Code'],
        'fields': {
            'Ref_Key': str,
            'Description': str,
            'Code': str,
            'ИмяПользователя': str,
            'Email': str
        }
    },
    'Catalog_Организации': {
        'required': ['Description', 'Code'],
        'fields': {
            'Ref_Key': str,
            'Description': str,
            'Code': str,
            'ИНН': str,
            'КПП': str
        }
    },
    'Catalog_Номенклатура': {
        'required': ['Description', 'Code'],
        'fields': {
            'Ref_Key': str,
            'Description': str,
            'Code': str,
            'Артикул': str,
            'Цена': (int, float)
        }
    }
}


def check_auth(f):
    """Decorator для проверки HTTP Basic Auth"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = request.authorization
        if not auth or auth.username != ODATA_USERNAME or auth.password != ODATA_PASSWORD:
            return odata_error('Unauthorized', 401)
        return f(*args, **kwargs)
    return decorated_function


def odata_error(message, status_code=400):
    """Форматирование ошибки в OData формате"""
    error_response = {
        "odata.error": {
            "code": str(status_code),
            "message": {
                "lang": "ru-RU",
                "value": message
            }
        }
    }
    return jsonify(error_response), status_code


def odata_response(data, is_collection=True):
    """Форматирование ответа в OData v3 формате"""
    if is_collection:
        return jsonify({
            "d": {
                "results": data
            }
        })
    else:
        return jsonify({
            "d": data
        })


def validate_entity(entity_type, data):
    """Валидация данных сущности"""
    if entity_type not in ENTITY_SCHEMAS:
        return False, f"Unknown entity type: {entity_type}"

    schema = ENTITY_SCHEMAS[entity_type]

    # Проверка обязательных полей
    for field in schema['required']:
        if field not in data or not data[field]:
            return False, f"Required field missing: {field}"

    return True, None


def parse_entity_url(entity_type_str):
    """
    Парсинг строки типа 'Catalog_Пользователи' в entity type
    """
    if entity_type_str not in databases:
        return None
    return entity_type_str


def parse_entity_id(id_str):
    """
    Парсинг ID из URL формата: guid'550e8400-e29b-41d4-a716-446655440000'
    """
    if id_str.startswith("guid'") and id_str.endswith("'"):
        return id_str[5:-1]
    return id_str


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'database': DB_NAME,
        'entities': list(databases.keys()),
        'timestamp': datetime.utcnow().isoformat()
    })


@app.route('/odata/standard.odata/$metadata', methods=['GET'])
def metadata():
    """
    OData v3 Metadata endpoint
    Возвращает XML с описанием доступных entity types
    """
    metadata_xml = '''<?xml version="1.0" encoding="utf-8"?>
<edmx:Edmx Version="1.0" xmlns:edmx="http://schemas.microsoft.com/ado/2007/06/edmx">
  <edmx:DataServices m:DataServiceVersion="3.0" xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata">
    <Schema Namespace="StandardODATA" xmlns="http://schemas.microsoft.com/ado/2009/11/edm">

      <EntityType Name="Catalog_Пользователи">
        <Key>
          <PropertyRef Name="Ref_Key"/>
        </Key>
        <Property Name="Ref_Key" Type="Edm.Guid" Nullable="false"/>
        <Property Name="Description" Type="Edm.String"/>
        <Property Name="Code" Type="Edm.String"/>
        <Property Name="ИмяПользователя" Type="Edm.String"/>
        <Property Name="Email" Type="Edm.String"/>
      </EntityType>

      <EntityType Name="Catalog_Организации">
        <Key>
          <PropertyRef Name="Ref_Key"/>
        </Key>
        <Property Name="Ref_Key" Type="Edm.Guid" Nullable="false"/>
        <Property Name="Description" Type="Edm.String"/>
        <Property Name="Code" Type="Edm.String"/>
        <Property Name="ИНН" Type="Edm.String"/>
        <Property Name="КПП" Type="Edm.String"/>
      </EntityType>

      <EntityType Name="Catalog_Номенклатура">
        <Key>
          <PropertyRef Name="Ref_Key"/>
        </Key>
        <Property Name="Ref_Key" Type="Edm.Guid" Nullable="false"/>
        <Property Name="Description" Type="Edm.String"/>
        <Property Name="Code" Type="Edm.String"/>
        <Property Name="Артикул" Type="Edm.String"/>
        <Property Name="Цена" Type="Edm.Decimal"/>
      </EntityType>

      <EntityContainer Name="StandardODATA" m:IsDefaultEntityContainer="true">
        <EntitySet Name="Catalog_Пользователи" EntityType="StandardODATA.Catalog_Пользователи"/>
        <EntitySet Name="Catalog_Организации" EntityType="StandardODATA.Catalog_Организации"/>
        <EntitySet Name="Catalog_Номенклатура" EntityType="StandardODATA.Catalog_Номенклатура"/>
      </EntityContainer>

    </Schema>
  </edmx:DataServices>
</edmx:Edmx>'''

    return metadata_xml, 200, {'Content-Type': 'application/xml; charset=utf-8'}


@app.route('/odata/standard.odata/<entity_type>', methods=['GET'])
@check_auth
def list_entities(entity_type):
    """
    Получение списка сущностей
    GET /odata/standard.odata/Catalog_Пользователи
    """
    parsed_type = parse_entity_url(entity_type)
    if not parsed_type:
        return odata_error(f"Unknown entity type: {entity_type}", 404)

    entities = list(databases[parsed_type].values())
    return odata_response(entities, is_collection=True)


@app.route('/odata/standard.odata/<entity_type>(<entity_id>)', methods=['GET'])
@check_auth
def get_entity(entity_type, entity_id):
    """
    Получение конкретной сущности по ID
    GET /odata/standard.odata/Catalog_Пользователи(guid'550e8400-e29b-41d4-a716-446655440000')
    """
    parsed_type = parse_entity_url(entity_type)
    if not parsed_type:
        return odata_error(f"Unknown entity type: {entity_type}", 404)

    parsed_id = parse_entity_id(entity_id)

    if parsed_id not in databases[parsed_type]:
        return odata_error(f"Entity not found: {parsed_id}", 404)

    entity = databases[parsed_type][parsed_id]
    return odata_response(entity, is_collection=False)


@app.route('/odata/standard.odata/<entity_type>', methods=['POST'])
@check_auth
def create_entity(entity_type):
    """
    Создание новой сущности
    POST /odata/standard.odata/Catalog_Пользователи
    Body: {"Description": "Иванов", "Code": "00001", ...}
    """
    parsed_type = parse_entity_url(entity_type)
    if not parsed_type:
        return odata_error(f"Unknown entity type: {entity_type}", 404)

    data = request.get_json()
    if not data:
        return odata_error("Request body is empty", 400)

    # Валидация
    valid, error_msg = validate_entity(parsed_type, data)
    if not valid:
        return odata_error(error_msg, 400)

    # Генерация Ref_Key если не указан
    if 'Ref_Key' not in data:
        data['Ref_Key'] = str(uuid.uuid4())

    entity_id = data['Ref_Key']

    # Проверка на дубликаты
    if entity_id in databases[parsed_type]:
        return odata_error(f"Entity with Ref_Key {entity_id} already exists", 409)

    # Сохранение
    databases[parsed_type][entity_id] = data

    return odata_response(data, is_collection=False), 201


@app.route('/odata/standard.odata/<entity_type>(<entity_id>)', methods=['PATCH'])
@check_auth
def update_entity(entity_type, entity_id):
    """
    Обновление существующей сущности
    PATCH /odata/standard.odata/Catalog_Пользователи(guid'550e8400-e29b-41d4-a716-446655440000')
    Body: {"Email": "new@example.com"}
    """
    parsed_type = parse_entity_url(entity_type)
    if not parsed_type:
        return odata_error(f"Unknown entity type: {entity_type}", 404)

    parsed_id = parse_entity_id(entity_id)

    if parsed_id not in databases[parsed_type]:
        return odata_error(f"Entity not found: {parsed_id}", 404)

    data = request.get_json()
    if not data:
        return odata_error("Request body is empty", 400)

    # Обновление полей
    entity = databases[parsed_type][parsed_id]
    entity.update(data)

    # Ref_Key не должен изменяться
    entity['Ref_Key'] = parsed_id

    return odata_response(entity, is_collection=False)


@app.route('/odata/standard.odata/<entity_type>(<entity_id>)', methods=['DELETE'])
@check_auth
def delete_entity(entity_type, entity_id):
    """
    Удаление сущности
    DELETE /odata/standard.odata/Catalog_Пользователи(guid'550e8400-e29b-41d4-a716-446655440000')
    """
    parsed_type = parse_entity_url(entity_type)
    if not parsed_type:
        return odata_error(f"Unknown entity type: {entity_type}", 404)

    parsed_id = parse_entity_id(entity_id)

    if parsed_id not in databases[parsed_type]:
        return odata_error(f"Entity not found: {parsed_id}", 404)

    del databases[parsed_type][parsed_id]

    return '', 204


@app.errorhandler(404)
def not_found(error):
    return odata_error("Resource not found", 404)


@app.errorhandler(500)
def internal_error(error):
    return odata_error("Internal server error", 500)


if __name__ == '__main__':
    print(f"Starting Mock 1C OData Server")
    print(f"Database: {DB_NAME}")
    print(f"Port: {PORT}")
    print(f"Username: {ODATA_USERNAME}")
    print(f"Available entities: {list(databases.keys())}")

    app.run(host='0.0.0.0', port=PORT, debug=True)
