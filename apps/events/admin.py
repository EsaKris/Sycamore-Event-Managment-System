from django.contrib import admin

from .models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'year', 'status', 'registration_status', 'start_date', 'end_date', 'max_capacity')
    list_filter = ('status', 'registration_status', 'year')
    search_fields = ('title', 'theme', 'venue')
    prepopulated_fields = {'slug': ('title', 'year')}
