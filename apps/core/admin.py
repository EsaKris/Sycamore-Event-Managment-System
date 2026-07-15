from django.contrib import admin

from .models import AuditLog, Notification, SystemSettings


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'administrator', 'action', 'model_name', 'object_id', 'ip_address')
    list_filter = ('model_name',)
    search_fields = ('action', 'object_id', 'administrator__username')
    readonly_fields = [f.name for f in AuditLog._meta.fields]


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'level', 'created_at')
    list_filter = ('level',)
    search_fields = ('title', 'message')


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ('system_name', 'church_name', 'updated_at')

    def has_add_permission(self, request):
        return not SystemSettings.objects.exists()
