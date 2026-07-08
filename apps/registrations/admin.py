from django.contrib import admin

from .models import Registration


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = (
        'registration_number', 'person', 'event', 'category', 'worker_type',
        'department', 'status', 'is_returning_attendee', 'created_at',
    )
    list_filter = ('event', 'category', 'worker_type', 'status', 'is_returning_attendee')
    search_fields = ('registration_number', 'person__first_name', 'person__last_name', 'person__person_id')
    autocomplete_fields = ('person', 'event', 'department')
