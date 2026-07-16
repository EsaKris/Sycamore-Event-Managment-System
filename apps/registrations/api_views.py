from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.people.services import DuplicatePersonError

from .models import Registration
from .serializers import RegisterNewSerializer, RegisterReturningSerializer, RegistrationSerializer
from .services import AlreadyRegisteredError, RegistrationService


class RegistrationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    List/retrieve are plain read-only. Creation is deliberately NOT a
    standard POST /registrations/ — the spec's registration flow is a
    branch (new vs. returning attendee) with different validation and
    side effects for each, so it's two explicit actions instead of one
    endpoint trying to infer which branch from the payload shape.
    Both delegate to RegistrationService — the exact same dedup checks,
    notification triggers, and audit logging the dashboard wizard gets.
    """
    queryset = Registration.objects.select_related('person', 'event', 'department').all()
    serializer_class = RegistrationSerializer
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['registration_number', 'person__first_name', 'person__last_name', 'person__person_id']
    ordering_fields = ['created_at']

    def get_queryset(self):
        qs = super().get_queryset()
        event_id = self.request.query_params.get('event')
        category = self.request.query_params.get('category')
        if event_id:
            qs = qs.filter(event_id=event_id)
        if category:
            qs = qs.filter(category=category)
        return qs

    @action(detail=False, methods=['post'], url_path='register-new')
    def register_new(self, request):
        serializer = RegisterNewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        registration_fields = {
            'category': data['category'],
            'worker_type': data.get('worker_type') or '',
            'department': data.get('department'),
            'accommodation_requested': data.get('accommodation_requested', False),
        }

        try:
            result = RegistrationService.register_new_person(
                event=data['event'], person_fields=dict(data['person']), registration_fields=registration_fields,
            )
        except DuplicatePersonError as e:
            return Response({'detail': str(e)}, status=status.HTTP_409_CONFLICT)
        except Exception as e:  # registration-level validation (e.g. worker without department)
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(RegistrationSerializer(result.registration).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='register-returning')
    def register_returning(self, request):
        serializer = RegisterReturningSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        person = RegistrationService.find_returning_person(
            phone_number=data.get('phone_number', ''), email_address=data.get('email_address', ''),
            person_id=data.get('person_id', ''), qr_token=data.get('qr_token', ''),
        )
        if not person:
            return Response({'detail': 'No matching person found.'}, status=status.HTTP_404_NOT_FOUND)

        registration_fields = {
            'category': data['category'],
            'worker_type': data.get('worker_type') or '',
            'department': data.get('department'),
            'accommodation_requested': data.get('accommodation_requested', False),
        }
        updated_fields = dict(data['updated_person_fields']) if data.get('updated_person_fields') else None

        try:
            result = RegistrationService.register_returning_person(
                event=data['event'], person=person, updated_fields=updated_fields,
                registration_fields=registration_fields,
            )
        except AlreadyRegisteredError as e:
            return Response({'detail': str(e)}, status=status.HTTP_409_CONFLICT)
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(RegistrationSerializer(result.registration).data, status=status.HTTP_201_CREATED)
