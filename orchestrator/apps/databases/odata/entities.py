# orchestrator/apps/databases/odata/entities.py
"""
Маппинг типов сущностей 1С OData.

1С использует специфичную структуру URL для разных типов объектов.
"""

from typing import Dict


# Типы сущностей 1С
ENTITY_TYPE_CATALOG = 'Catalog'
ENTITY_TYPE_DOCUMENT = 'Document'
ENTITY_TYPE_INFORMATION_REGISTER = 'InformationRegister'
ENTITY_TYPE_ACCUMULATION_REGISTER = 'AccumulationRegister'
ENTITY_TYPE_ACCOUNTING_REGISTER = 'AccountingRegister'
ENTITY_TYPE_CALCULATION_REGISTER = 'CalculationRegister'


# Mapping типов сущностей
ENTITY_TYPES = {
    'catalog': ENTITY_TYPE_CATALOG,
    'document': ENTITY_TYPE_DOCUMENT,
    'information_register': ENTITY_TYPE_INFORMATION_REGISTER,
    'accumulation_register': ENTITY_TYPE_ACCUMULATION_REGISTER,
    'accounting_register': ENTITY_TYPE_ACCOUNTING_REGISTER,
    'calculation_register': ENTITY_TYPE_CALCULATION_REGISTER,
}


# Часто используемые справочники 1С
COMMON_CATALOGS = [
    'Пользователи',
    'Организации',
    'Контрагенты',
    'Номенклатура',
    'Склады',
    'Подразделения',
    'Сотрудники',
]


# Часто используемые документы 1С
COMMON_DOCUMENTS = [
    'РеализацияТоваровУслуг',
    'ПоступлениеТоваровУслуг',
    'СчетФактураВыданный',
    'СчетФактураПолученный',
    'ПриходныйКассовыйОрдер',
    'РасходныйКассовыйОрдер',
]


def get_entity_url_part(entity_type: str, entity_name: str) -> str:
    """
    Получить URL часть для сущности 1С.

    Args:
        entity_type: Тип сущности ('Catalog', 'Document', etc.)
        entity_name: Название сущности (например, 'Пользователи')

    Returns:
        str: URL часть (например, 'Catalog_Пользователи')

    Example:
        >>> get_entity_url_part('Catalog', 'Пользователи')
        'Catalog_Пользователи'
    """
    return f"{entity_type}_{entity_name}"


def parse_entity_url_part(url_part: str) -> Dict[str, str]:
    """
    Распарсить URL часть сущности.

    Args:
        url_part: URL часть (например, 'Catalog_Пользователи')

    Returns:
        dict: {'entity_type': '...', 'entity_name': '...'}

    Example:
        >>> parse_entity_url_part('Catalog_Пользователи')
        {'entity_type': 'Catalog', 'entity_name': 'Пользователи'}
    """
    parts = url_part.split('_', 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid entity URL part: {url_part}")

    return {
        'entity_type': parts[0],
        'entity_name': parts[1]
    }
