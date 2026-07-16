from rest_framework import serializers

from .models import Event


class EventSerializer(serializers.ModelSerializer):
    is_registration_open = serializers.BooleanField(read_only=True)
    is_full = serializers.BooleanField(read_only=True)
    registration_count = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            'id', 'title', 'slug', 'theme', 'description', 'year', 'venue',
            'start_date', 'end_date', 'registration_status', 'max_capacity',
            'color_theme', 'status', 'is_registration_open', 'is_full', 'registration_count',
        ]

    def get_registration_count(self, obj):
        return obj.registrations.count()
