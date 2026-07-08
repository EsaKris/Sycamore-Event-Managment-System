from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'administrator', 'action', 'model_name', 'object_id', 'ip_address')
    list_filter = ('model_name',)
    search_fields = ('action', 'object_id', 'administrator__username')
    readonly_fields = [f.name for f in AuditLog._meta.fields]
