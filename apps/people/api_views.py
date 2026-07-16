from rest_framework import viewsets
from rest_framework.filters import SearchFilter

from .models import Person
from .serializers import PersonSerializer


class PersonViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only, and deliberately so: Person is never created or edited
    directly through the API. Creating one bypasses the dedup service
    (PersonService) that's the entire point of the data model — new
    people only ever come into existence through a Registration (see
    apps.registrations.api_views), exactly like the dashboard wizard.
    """
    queryset = Person.objects.all()
    serializer_class = PersonSerializer
    filter_backends = [SearchFilter]
    search_fields = ['first_name', 'last_name', 'phone_number', 'email_address', 'person_id']
    lookup_field = 'person_id'
