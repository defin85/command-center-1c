"""
Custom JWT views for Go API Gateway compatibility.

Provides custom TokenObtainPairSerializer that adds username and roles
to JWT claims, ensuring compatibility with Go authentication middleware.
"""
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom TokenObtainPairSerializer that adds username and roles to JWT claims.

    Go API Gateway expects:
    - user_id: string (Django sends int, we convert)
    - username: string
    - roles: []string

    This ensures compatibility between Django-generated tokens and Go JWT validation.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Add custom claims for Go API Gateway compatibility
        # Convert user_id to string (Go expects string, Django uses int)
        token['user_id'] = str(user.id)
        token['username'] = user.username

        # Get user roles/groups
        roles = []
        if user.is_superuser:
            roles.append('admin')
        if user.is_staff:
            roles.append('staff')

        # Add group names as roles
        if hasattr(user, 'groups'):
            roles.extend([group.name for group in user.groups.all()])

        token['roles'] = roles

        return token


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Custom TokenObtainPairView that uses CustomTokenObtainPairSerializer.

    Generates JWT tokens with custom claims (username, roles) compatible
    with Go API Gateway authentication middleware.
    """
    serializer_class = CustomTokenObtainPairSerializer
