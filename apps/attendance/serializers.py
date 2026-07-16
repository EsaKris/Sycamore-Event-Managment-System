from rest_framework import serializers

from apps.events.models import Event
from apps.people.serializers import PersonSerializer

from .models import Attendance, AttendanceSession


class AttendanceSessionSerializer(serializers.ModelSerializer):
    event_title = serializers.CharField(source='event.title', read_only=True)

    class Meta:
        model = AttendanceSession
        fields = ['id', 'event', 'event_title', 'label', 'session_type', 'date', 'is_active']


class AttendanceSerializer(serializers.ModelSerializer):
    person = PersonSerializer(read_only=True)
    session_label = serializers.CharField(source='session.label', read_only=True)
    scanned_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Attendance
        fields = [
            'id', 'person', 'registration', 'event', 'session', 'session_label',
            'check_type', 'scanned_by_name', 'location', 'created_at',
        ]
        read_only_fields = fields  # writes only ever go through the /scan/ action

    def get_scanned_by_name(self, obj):
        if not obj.scanned_by:
            return None
        return obj.scanned_by.get_full_name() or obj.scanned_by.username


class ScanRequestSerializer(serializers.Serializer):
    code = serializers.CharField()
    event = serializers.PrimaryKeyRelatedField(queryset=Event.objects.all())
    session = serializers.PrimaryKeyRelatedField(queryset=AttendanceSession.objects.all())
    check_type = serializers.ChoiceField(choices=[('check_in', 'Check-in'), ('check_out', 'Check-out')])
    location = serializers.CharField(required=False, allow_blank=True, default='')
