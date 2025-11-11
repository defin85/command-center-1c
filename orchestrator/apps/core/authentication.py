"""
Custom JWT Authentication для service-to-service requests.
Не требует существования пользователя в БД для service tokens.
"""
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from django.contrib.auth.models import AnonymousUser


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
        self.is_superuser = False
        
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
