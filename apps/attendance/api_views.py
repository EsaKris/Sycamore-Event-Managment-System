from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Attendance, AttendanceSession
from .serializers import AttendanceSerializer, AttendanceSessionSerializer, ScanRequestSerializer
from .services import AttendanceService


class AttendanceSessionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AttendanceSession.objects.all()
    serializer_class = AttendanceSessionSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        event_id = self.request.query_params.get('event')
        if event_id:
            qs = qs.filter(event_id=event_id)
        return qs


class AttendanceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    List/retrieve are read-only history. The real point of exposing
    Attendance via the API is the `/scan/` action below — it's the exact
    same AttendanceService.scan() the web QR scanner calls, so a
    companion mobile app gets identical duplicate-scan/already-checked-in/
    not-registered handling for free, not a reimplementation of that logic.
    """
    queryset = Attendance.objects.select_related('person', 'event', 'session', 'scanned_by').all()
    serializer_class = AttendanceSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        event_id = self.request.query_params.get('event')
        session_id = self.request.query_params.get('session')
        check_type = self.request.query_params.get('check_type')
        if event_id:
            qs = qs.filter(event_id=event_id)
        if session_id:
            qs = qs.filter(session_id=session_id)
        if check_type:
            qs = qs.filter(check_type=check_type)
        return qs

    @action(detail=False, methods=['post'])
    def scan(self, request):
        serializer = ScanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        outcome = AttendanceService.scan(
            code=data['code'], event=data['event'], session=data['session'],
            check_type=data['check_type'], scanner=request.user, location=data.get('location', ''),
        )

        payload = {
            'status': outcome.status.value,
            'ok': outcome.ok,
            'is_warning': outcome.is_warning,
            'message': outcome.message,
            'attendance': AttendanceSerializer(outcome.attendance).data if outcome.attendance else None,
        }
        if outcome.person:
            from apps.people.serializers import PersonSerializer
            payload['person'] = PersonSerializer(outcome.person, context={'request': request}).data

        http_status = status.HTTP_200_OK if outcome.ok else (
            status.HTTP_404_NOT_FOUND if outcome.status.value == 'not_found' else status.HTTP_409_CONFLICT
        )
        return Response(payload, status=http_status)
