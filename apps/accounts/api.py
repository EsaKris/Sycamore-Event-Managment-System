from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.contrib.auth import authenticate


@api_view(['POST'])
@permission_classes([AllowAny])
def obtain_token(request):
    """
    POST {"username": "...", "password": "..."} -> {"token": "...", ...}

    Deliberately not DRF's stock ObtainAuthToken: that view doesn't know
    about `is_active_administrator` or `must_reset_password`, both of
    which need to block API access the same way they block the
    dashboard. A temp-password administrator gets a clear error instead
    of a working token that lets them skip the forced password reset.
    """
    username = request.data.get('username', '')
    password = request.data.get('password', '')
    user = authenticate(request, username=username, password=password)

    if user is None:
        return Response({'detail': 'Invalid username or password.'}, status=401)
    if not user.is_active_administrator:
        return Response({'detail': 'This administrator account has been deactivated.'}, status=403)
    if user.must_reset_password:
        return Response(
            {'detail': 'This account has a temporary password. Sign in to the dashboard first to set a new one.'},
            status=403,
        )

    token, _ = Token.objects.get_or_create(user=user)
    return Response({
        'token': token.key,
        'username': user.username,
        'full_name': user.get_full_name(),
        'role': user.role,
        'role_display': user.get_role_display(),
    })
