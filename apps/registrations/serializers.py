from rest_framework import serializers

from apps.departments.models import Department
from apps.events.models import Event
from apps.people.models import Person
from apps.people.serializers import PersonSerializer

from .models import Registration


class RegistrationSerializer(serializers.ModelSerializer):
    person = PersonSerializer(read_only=True)
    event_title = serializers.CharField(source='event.title', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True, default=None)
    card_label = serializers.CharField(read_only=True)

    class Meta:
        model = Registration
        fields = [
            'id', 'registration_number', 'person', 'event', 'event_title',
            'category', 'worker_type', 'department', 'department_name', 'card_label',
            'is_returning_attendee', 'accommodation_requested', 'status',
            'badge_label', 'created_at',
        ]
        read_only_fields = fields  # writes go through the action endpoints below, never a plain PATCH/PUT


class PersonInputSerializer(serializers.Serializer):
    """Not a ModelSerializer — this never touches the database directly.
    apps.people.services.PersonService owns creation (dedup check first)."""

    first_name = serializers.CharField(max_length=100)
    middle_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=100)
    gender = serializers.ChoiceField(choices=[('male', 'Male'), ('female', 'Female')])
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    marital_status = serializers.CharField(required=False, allow_blank=True)
    phone_number = serializers.CharField(max_length=20)
    alternative_phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    email_address = serializers.EmailField(required=False, allow_blank=True)
    residential_address = serializers.CharField(required=False, allow_blank=True)
    state = serializers.CharField(max_length=100, required=False, allow_blank=True)
    local_government = serializers.CharField(max_length=100, required=False, allow_blank=True)
    country = serializers.CharField(max_length=100, required=False, default='Nigeria')
    church_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    church_address = serializers.CharField(required=False, allow_blank=True)
    pastors_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    occupation = serializers.CharField(max_length=255, required=False, allow_blank=True)
    emergency_contact_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    emergency_phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    emergency_relationship = serializers.CharField(max_length=100, required=False, allow_blank=True)
    medical_notes = serializers.CharField(required=False, allow_blank=True)
    dietary_notes = serializers.CharField(required=False, allow_blank=True)


class RegisterNewSerializer(serializers.Serializer):
    """POST body for 'NO, I have not attended before' — mirrors the
    dashboard wizard's own branch exactly."""
    event = serializers.PrimaryKeyRelatedField(queryset=Event.objects.all())
    person = PersonInputSerializer()
    category = serializers.ChoiceField(choices=[('participant', 'Participant'), ('worker', 'Worker')])
    worker_type = serializers.ChoiceField(choices=[('member', 'Member'), ('pastor', 'Pastor')], required=False, allow_null=True)
    department = serializers.PrimaryKeyRelatedField(queryset=Department.objects.all(), required=False, allow_null=True)
    accommodation_requested = serializers.BooleanField(required=False, default=False)


class RegisterReturningSerializer(serializers.Serializer):
    """POST body for 'YES, I have attended before'. Exactly one of
    phone_number/email_address/person_id/qr_token must resolve to an
    existing Person — same identifiers the QR scanner and dashboard
    search accept."""
    phone_number = serializers.CharField(required=False, allow_blank=True)
    email_address = serializers.CharField(required=False, allow_blank=True)
    person_id = serializers.CharField(required=False, allow_blank=True)
    qr_token = serializers.CharField(required=False, allow_blank=True)

    event = serializers.PrimaryKeyRelatedField(queryset=Event.objects.all())
    category = serializers.ChoiceField(choices=[('participant', 'Participant'), ('worker', 'Worker')])
    worker_type = serializers.ChoiceField(choices=[('member', 'Member'), ('pastor', 'Pastor')], required=False, allow_null=True)
    department = serializers.PrimaryKeyRelatedField(queryset=Department.objects.all(), required=False, allow_null=True)
    accommodation_requested = serializers.BooleanField(required=False, default=False)

    # Optional — updates the Person record with any changed details, same as the dashboard wizard's edit step.
    updated_person_fields = PersonInputSerializer(required=False)

    def validate(self, data):
        if not any([data.get('phone_number'), data.get('email_address'), data.get('person_id'), data.get('qr_token')]):
            raise serializers.ValidationError(
                'Provide at least one of phone_number, email_address, person_id, or qr_token to find the person.'
            )
        return data
