from django.contrib import admin

from .models import Person


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ('person_id', 'full_name', 'phone_number', 'email_address', 'state', 'country', 'status', 'created_at')
    search_fields = ('person_id', 'first_name', 'last_name', 'phone_number', 'email_address')
    list_filter = ('status', 'gender', 'state', 'country')
    readonly_fields = ('person_id', 'qr_token', 'created_at', 'updated_at')
    ordering = ('-created_at',)
