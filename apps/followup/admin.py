from django.contrib import admin

from .models import FollowUp


@admin.register(FollowUp)
class FollowUpAdmin(admin.ModelAdmin):
    list_display = ('person', 'follow_up_type', 'status', 'outcome', 'next_follow_up_date', 'officer_assigned', 'created_at')
    list_filter = ('status', 'follow_up_type', 'outcome', 'interest_level', 'event')
    search_fields = ('person__first_name', 'person__last_name', 'person__phone_number', 'person__person_id', 'remarks')
    autocomplete_fields = ('person', 'event', 'officer_assigned', 'logged_by')
    date_hierarchy = 'created_at'
