from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import OperationTemplate
from .serializers import OperationTemplateSerializer
from .engine import TemplateValidator, TemplateValidationError, TemplateRenderError


class OperationTemplateViewSet(viewsets.ModelViewSet):
    queryset = OperationTemplate.objects.all()
    serializer_class = OperationTemplateSerializer
    filterset_fields = ['operation_type', 'is_active']

    @action(detail=True, methods=['post'])
    def validate(self, request, pk=None):
        """
        Validate template schema and security.

        POST /api/v1/templates/{id}/validate/

        Returns:
            {"valid": true} or {"valid": false, "errors": [...]}
        """
        template = self.get_object()
        validator = TemplateValidator()

        try:
            validator.validate_template(template)
            return Response({
                'valid': True,
                'message': 'Template is valid'
            })
        except TemplateValidationError as exc:
            return Response({
                'valid': False,
                'errors': str(exc)
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def validate_data(self, request):
        """
        Validate template_data only (without saving to DB).

        POST /api/v1/templates/validate_data/
        {
            "template_data": {"Name": "{{user_name}}"}
        }

        Returns:
            {"valid": true, "errors": []}
        """
        template_data = request.data.get('template_data')

        if not template_data:
            return Response({
                'valid': False,
                'errors': ['template_data is required']
            }, status=status.HTTP_400_BAD_REQUEST)

        validator = TemplateValidator()
        errors = validator.validate_template_data_only(template_data)

        if errors:
            return Response({
                'valid': False,
                'errors': errors
            }, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'valid': True,
            'errors': []
        })

    @action(detail=True, methods=['post'])
    def render(self, request, pk=None):
        """
        Render template with provided context.

        POST /api/v1/templates/{id}/render/
        {
            "context": {
                "user_name": "Alice",
                "database_name": "db001",
                "is_active": true
            },
            "validate": true  # Optional, default: true
        }

        Returns rendered template result.
        """
        from .engine import TemplateRenderer

        template = self.get_object()
        context_data = request.data.get('context', {})
        validate = request.data.get('validate', True)

        try:
            renderer = TemplateRenderer()
            result = renderer.render(template, context_data, validate=validate)

            return Response({
                'success': True,
                'result': result,
                'template_id': str(template.id),
                'template_name': template.name
            })

        except TemplateValidationError as exc:
            return Response({
                'success': False,
                'error': 'validation_error',
                'message': str(exc)
            }, status=status.HTTP_400_BAD_REQUEST)

        except TemplateRenderError as exc:
            return Response({
                'success': False,
                'error': 'render_error',
                'message': str(exc)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
