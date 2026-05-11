from django.contrib.auth import logout
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError


class JWTSessionMiddleware:
    """Logs the user out when the JWT refresh token in their session is missing or expired."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            access_str = request.session.get('jwt_access')

            if not access_str:
                logout(request)
            else:
                try:
                    AccessToken(access_str)
                except TokenError:
                    request.session.pop('jwt_refresh', None)
                    request.session.pop('jwt_access', None)
                    logout(request)

        return self.get_response(request)
