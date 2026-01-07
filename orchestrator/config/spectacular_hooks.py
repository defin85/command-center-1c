from __future__ import annotations

from typing import Any


def remove_nullable_oneof_nullenum(result: dict[str, Any], generator: Any, request: Any, public: bool):
    """
    orval (TypeScript) can't handle some redundant "nullable + oneOf(null)" constructs and may
    fail with duplicate schema name collisions.

    drf-spectacular can emit:
      nullable: true
      oneOf: [<schema>, NullEnum]

    Since NullEnum already encodes nullability, drop the redundant "nullable: true".
    """

    def _walk(node: Any):
        if isinstance(node, dict):
            if node.get("nullable") is True and "oneOf" in node:
                one_of = node.get("oneOf")
                if isinstance(one_of, list) and any(
                    isinstance(item, dict) and item.get("$ref") == "#/components/schemas/NullEnum"
                    for item in one_of
                ):
                    node.pop("nullable", None)
            for value in node.values():
                _walk(value)
            return
        if isinstance(node, list):
            for item in node:
                _walk(item)

    components = result.get("components") or {}
    schemas = components.get("schemas") or {}
    _walk(schemas)
    return result

