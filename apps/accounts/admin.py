from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ('username', 'get_full_name', 'role', 'is_active_administrator', 'is_superuser', 'last_login')
    list_filter = ('role', 'is_active_administrator', 'is_superuser')
    fieldsets = DjangoUserAdmin.fieldsets + (
        ('SEMS Administrator Info', {
            'fields': ('person', 'role', 'must_reset_password', 'is_active_administrator'),
        }),
    )
