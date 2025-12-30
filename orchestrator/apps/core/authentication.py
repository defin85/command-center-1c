"""
Custom JWT Authentication для service-to-service requests.
Не требует существования пользователя в БД для service tokens.
"""
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken


class ServiceUser:
    """
    Фиктивный пользователь для service-to-service authentication.
    Используется когда user_id начинается с 'service:'.
    """
    def __init__(self, service_name):
        self.service_name = service_name
        self.is_authenticated = True
        self.is_active = True
        self.is_staff = False
        
    @property
    def username(self):
        return f"service:{self.service_name}"
    
    @property
    def id(self):
        return f"service:{self.service_name}"
    
    def __str__(self):
        return f"ServiceUser({self.service_name})"


class ServiceJWTAuthentication(JWTAuthentication):
    """
    Custom JWT Authentication для поддержки service tokens.

    Если user_id начинается с 'service:', создаёт ServiceUser вместо
    загрузки из БД. Это позволяет Worker и другим сервисам аутентифицироваться
    без создания реальных пользователей в БД.
    """

    def authenticate(self, request):
        """Override to add debug logging."""
        import logging
        logger = logging.getLogger(__name__)

        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        logger.debug("ServiceJWT authenticate called", extra={
            "auth_header_preview": auth_header[:50] if auth_header else 'missing',
            "path": request.path,
        })

        try:
            result = super().authenticate(request)
            if result:
                user, token = result
                logger.info("ServiceJWT authentication successful", extra={
                    "user": str(user),
                    "is_service": hasattr(user, 'service_name'),
                })
            return result
        except Exception as e:
            logger.error(f"ServiceJWT authentication failed: {e}", extra={
                "error_type": type(e).__name__,
                "auth_header_preview": auth_header[:50] if auth_header else 'missing',
            })
            raise

    def get_user(self, validated_token):
        """
        Attempts to find and return a user using the given validated token.
        
        For service tokens (user_id starts with 'service:'), returns ServiceUser.
        For regular tokens, uses standard user lookup.
        """
        try:
            user_id = validated_token.get(self.get_user_id_claim())
        except KeyError:
            raise InvalidToken('Token contained no recognizable user identification')

        # Check if this is a service token
        if isinstance(user_id, str) and user_id.startswith('service:'):
            service_name = user_id.replace('service:', '', 1)
            return ServiceUser(service_name)
        
        # Regular user token - use standard lookup
        return super().get_user(validated_token)
    
    def get_user_id_claim(self):
        """Get the claim name used for user ID"""
        from rest_framework_simplejwt.settings import api_settings
        return api_settings.USER_ID_CLAIM


# drf-spectacular OpenAPI integration
#
# Ensures that ServiceJWTAuthentication is represented as HTTP Bearer (JWT)
# in the exported OpenAPI spec (contracts/orchestrator/openapi.yaml).
try:
    from drf_spectacular.extensions import OpenApiAuthenticationExtension
except Exception:  # pragma: no cover
    OpenApiAuthenticationExtension = None


if OpenApiAuthenticationExtension is not None:
    class ServiceJWTAuthenticationScheme(OpenApiAuthenticationExtension):
        target_class = 'apps.core.authentication.ServiceJWTAuthentication'
        name = 'bearerAuth'

        def get_security_definition(self, auto_schema):
            return {
                'type': 'http',
                'scheme': 'bearer',
                'bearerFormat': 'JWT',
            }
