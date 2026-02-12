from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.templates.template_runtime import TemplateResolveError, resolve_runtime_template

from .permissions import IsInternalService
from .serializers import TemplateRenderRequestSerializer
from .views_common import exclude_schema, logger


def _template_lookup_query_params(request):
    template_id = str(request.query_params.get("template_id") or "").strip()
    template_exposure_id = str(request.query_params.get("template_exposure_id") or "").strip()
    raw_template_exposure_revision = str(request.query_params.get("template_exposure_revision") or "").strip()
    template_exposure_revision = None
    if template_id:
        template_id = template_id.strip()
    if template_exposure_id:
        template_exposure_id = template_exposure_id.strip()
    if raw_template_exposure_revision:
        try:
            parsed_revision = int(raw_template_exposure_revision)
        except (TypeError, ValueError):
            return None, None, None, Response(
                {
                    "success": False,
                    "error": {
                        "template_exposure_revision": "Must be a positive integer.",
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if parsed_revision < 1:
            return None, None, None, Response(
                {
                    "success": False,
                    "error": {
                        "template_exposure_revision": "Must be greater than or equal to 1.",
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        template_exposure_revision = parsed_revision
    if not template_id and not template_exposure_id:
        return None, None, None, Response(
            {
                "success": False,
                "error": {
                    "template_id": "This query parameter is required when template_exposure_id is absent",
                    "template_exposure_id": "This query parameter is required when template_id is absent",
                },
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    return template_id or None, template_exposure_id or None, template_exposure_revision, None


@exclude_schema
@api_view(["GET"])
@permission_classes([IsInternalService])
def get_template(request):
    """
    GET /api/v2/internal/get-template?template_id=X

    Get template data for Go Worker.
    Returns template definition including template_data for rendering.

    Query params:
        template_id: str (optional; required when template_exposure_id absent)
        template_exposure_id: uuid (optional; required when template_id absent)
        template_exposure_revision: int>=1 (optional; drift check)

    Response:
    {
        "success": true,
        "template": {
            "id": "create_document",
            "name": "Create Document Template",
            "operation_type": "create",
            "target_entity": "Document.ЗаказКлиента",
            "template_data": {...},
            "version": 1,
            "is_active": true
        }
    }
    """
    template_id, template_exposure_id, template_exposure_revision, error_response = _template_lookup_query_params(request)
    if error_response is not None:
        return error_response

    try:
        template = resolve_runtime_template(
            template_alias=template_id,
            template_exposure_id=template_exposure_id,
            expected_exposure_revision=template_exposure_revision,
            require_active=False,
            require_published=False,
        )
    except TemplateResolveError as exc:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if exc.code == "TEMPLATE_NOT_FOUND"
            else status.HTTP_400_BAD_REQUEST
        )
        return Response({"success": False, "error": f"{exc.code}: {exc.message}"}, status=status_code)

    template_ref = template_exposure_id or template_id or template.id
    if not template.is_active:
        logger.warning(f"Template {template_ref} is inactive")
    if template.exposure_status != "published":
        logger.warning(
            "Template %s is not published (status=%s)",
            template_ref,
            template.exposure_status,
        )

    template_data = {
        "id": template.id,
        "name": template.name,
        "operation_type": template.operation_type,
        "target_entity": template.target_entity,
        "template_data": template.template_data,
        "version": 1,  # TODO: Add version field to model
        "is_active": template.is_active,
    }

    logger.debug(f"Template fetched: {template_ref}")

    return Response({"success": True, "template": template_data}, status=status.HTTP_200_OK)


@exclude_schema
@api_view(["POST"])
@permission_classes([IsInternalService])
def render_template(request):
    """
    POST /api/v2/internal/render-template?template_id=X

    Render template using Python Jinja2 (fallback for Go pongo2).
    Called by Go Worker when pongo2 encounters incompatible syntax.

    Query params:
        template_id: str (optional; required when template_exposure_id absent)
        template_exposure_id: uuid (optional; required when template_id absent)
        template_exposure_revision: int>=1 (optional; drift check)

    Request body:
    {
        "context": {
            "order_number": "12345",
            "items": [{"name": "Item1", "qty": 10}]
        }
    }

    Response:
    {
        "success": true,
        "rendered": {...},
        "error": ""
    }
    """
    from jinja2 import TemplateSyntaxError

    template_id, template_exposure_id, template_exposure_revision, error_response = _template_lookup_query_params(request)
    if error_response is not None:
        return error_response

    # Validate request
    req_serializer = TemplateRenderRequestSerializer(data=request.data)
    if not req_serializer.is_valid():
        return Response({"success": False, "error": req_serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    context = req_serializer.validated_data["context"]

    # Get template
    try:
        template = resolve_runtime_template(
            template_alias=template_id,
            template_exposure_id=template_exposure_id,
            expected_exposure_revision=template_exposure_revision,
            require_active=False,
            require_published=False,
        )
    except TemplateResolveError as exc:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if exc.code == "TEMPLATE_NOT_FOUND"
            else status.HTTP_400_BAD_REQUEST
        )
        return Response({"success": False, "error": f"{exc.code}: {exc.message}"}, status=status_code)

    # Render template_data recursively
    try:
        rendered = _render_template_data(template.template_data, context)

        template_ref = template_exposure_id or template_id or template.id
        logger.debug(f"Template rendered: {template_ref}")

        return Response({"success": True, "rendered": rendered, "error": ""}, status=status.HTTP_200_OK)

    except TemplateSyntaxError as e:
        template_ref = template_exposure_id or template_id or template.id
        logger.error(f"Template syntax error in {template_ref}: {e}")
        return Response(
            {"success": False, "rendered": {}, "error": f"Template syntax error: {str(e)}"},
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        template_ref = template_exposure_id or template_id or template.id
        logger.error(f"Template render error in {template_ref}: {e}")
        return Response({"success": False, "rendered": {}, "error": f"Render error: {str(e)}"}, status=status.HTTP_200_OK)


def _render_template_data(data, context):
    """
    Recursively render Jinja2 templates in data structure.

    Supports:
    - Strings with {{ }} expressions
    - Nested dicts and lists
    - Non-template values (int, float, bool, None) are passed through

    Security:
    - Uses SandboxedEnvironment to prevent code injection
    - Blocks access to dangerous attributes and methods
    """
    from jinja2 import BaseLoader
    from jinja2.sandbox import SandboxedEnvironment

    # Create sandboxed Jinja2 environment for security
    env = SandboxedEnvironment(loader=BaseLoader())

    if isinstance(data, str):
        # Check if string contains template expressions
        if "{{" in data or "{%" in data:
            template = env.from_string(data)
            return template.render(context)
        return data

    if isinstance(data, dict):
        return {key: _render_template_data(value, context) for key, value in data.items()}

    if isinstance(data, list):
        return [_render_template_data(item, context) for item in data]

    # Return non-template values as-is
    return data
