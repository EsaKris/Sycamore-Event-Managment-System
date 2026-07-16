from rest_framework import serializers

from .models import Person


class PersonSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = Person
        fields = [
            'person_id', 'full_name', 'first_name', 'middle_name', 'last_name',
            'photo_url', 'gender', 'date_of_birth', 'marital_status',
            'phone_number', 'alternative_phone', 'email_address',
            'residential_address', 'state', 'local_government', 'country',
            'church_name', 'church_address', 'pastors_name', 'occupation',
            'status', 'created_at',
        ]
        read_only_fields = fields  # Person is never created/edited directly via the API — see Registration endpoints.

    def get_photo_url(self, obj):
        request = self.context.get('request')
        if obj.photo and request:
            return request.build_absolute_uri(obj.photo.url)
        return None
