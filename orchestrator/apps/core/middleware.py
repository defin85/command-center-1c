"""
Channels middleware for JWT authentication via query string.

Usage in asgi.py:
    from apps.core.middleware import JWTAuthMiddlewareStack

    application = ProtocolTypeRouter({
        "websocket": JWTAuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        ),
    })
"""
import logging
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger(__name__)


@database_sync_to_async
def get_user_from_token(token: str):
    """
    Validate JWT token and return user.

    Works with both regular user tokens and service tokens.
    """
    from rest_framework_simplejwt.authentication import JWTAuthentication
    from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
    from apps.core.authentication import ServiceUser

    if not token:
        return AnonymousUser()

    try:
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)

        # Get user_id from token
        user_id_claim = validated_token.get('user_id')

        # Check if this is a service token
        if isinstance(user_id_claim, str) and user_id_claim.startswith('service:'):
            service_name = user_id_claim.replace('service:', '', 1)
            return ServiceUser(service_name)

        # Regular user token
        user = jwt_auth.get_user(validated_token)
        return user

    except (InvalidToken, TokenError) as e:
        logger.warning(f"Invalid JWT token for WebSocket: {e}")
        return AnonymousUser()
    except Exception as e:
        logger.error(f"Error validating JWT token: {e}")
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """
    Middleware that authenticates WebSocket connections via JWT token.

    Token can be passed in:
    - Query string: ws://host/path/?token=<jwt_token>
    - Subprotocol: Not implemented yet
    """

    async def __call__(self, scope, receive, send):
        # Extract token from query string
        query_string = scope.get('query_string', b'').decode('utf-8')
        query_params = parse_qs(query_string)

        token = None
        if 'token' in query_params:
            token = query_params['token'][0]

        # Get user from token
        if token:
            scope['user'] = await get_user_from_token(token)
            logger.debug(f"WebSocket authenticated: user={scope['user']}")
        else:
            # Try session-based auth (from AuthMiddlewareStack)
            if 'user' not in scope or scope['user'].is_anonymous:
                scope['user'] = AnonymousUser()

        return await super().__call__(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    """
    Convenience wrapper that combines JWT auth with session auth.

    Tries JWT token first (from query string), then falls back to session.
    """
    from channels.auth import AuthMiddlewareStack
    return JWTAuthMiddleware(AuthMiddlewareStack(inner))
