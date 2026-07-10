from django.contrib import admin

from .models import Attendance, AttendanceSession


@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    list_display = ('label', 'event', 'session_type', 'date', 'is_active')
    list_filter = ('event', 'session_type', 'is_active')
    search_fields = ('label',)


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('person', 'event', 'session', 'check_type', 'scanned_by', 'created_at')
    list_filter = ('event', 'session', 'check_type')
    search_fields = ('person__first_name', 'person__last_name', 'person__person_id')
    autocomplete_fields = ('person', 'registration', 'event', 'session')
