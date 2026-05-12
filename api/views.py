from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .serializer import UserSerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def currentUser(request):
    serializer = UserSerializer(request.user)
    return Response(serializer.data)
