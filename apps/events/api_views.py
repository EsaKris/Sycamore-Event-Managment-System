from rest_framework import viewsets
from rest_framework.filters import OrderingFilter, SearchFilter

from .models import Event
from .serializers import EventSerializer


class EventViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only for now — creating/editing an Event involves banner/logo
    uploads and is infrequent enough that the dashboard form is the
    right tool. Exposed here so external tools (a church website, a
    companion app) can list events and check registration status.
    """
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['title', 'theme', 'venue']
    ordering_fields = ['year', 'start_date', 'created_at']
    lookup_field = 'pk'
