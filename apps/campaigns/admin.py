from django.contrib import admin

from .models import CampaignRecipient, EmailCampaign, EmailTemplate


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'template_type', 'is_active', 'created_by', 'created_at')
    list_filter = ('template_type', 'is_active')
    search_fields = ('name', 'subject')


class CampaignRecipientInline(admin.TabularInline):
    model = CampaignRecipient
    extra = 0
    readonly_fields = ('person', 'email_address', 'status', 'sent_at', 'opened_at', 'error_message')
    can_delete = False


@admin.register(EmailCampaign)
class EmailCampaignAdmin(admin.ModelAdmin):
    list_display = ('name', 'template', 'event', 'status', 'scheduled_at', 'sent_at', 'created_at')
    list_filter = ('status', 'event', 'target_returning')
    search_fields = ('name',)
    autocomplete_fields = ('template', 'event', 'target_department')
    inlines = [CampaignRecipientInline]
