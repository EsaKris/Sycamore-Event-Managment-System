from django import forms

from apps.departments.models import Department
from apps.events.models import Event, EventStatus
from apps.registrations.models import RegistrationCategory, WorkerType

from .models import EmailCampaign, EmailTemplate, ReturningFilter

TEXT = 'field-input'
SELECT = 'field-input field-select'
TEXTAREA = 'field-input field-textarea'

PLACEHOLDER_LEGEND = [
    '{{ first_name }}', '{{ last_name }}', '{{ full_name }}', '{{ person_id }}',
    '{{ church_name }}', '{{ phone_number }}', '{{ event_title }}',
    '{{ registration_number }}', '{{ category }}', '{{ department }}',
]


class EmailTemplateForm(forms.ModelForm):
    class Meta:
        model = EmailTemplate
        fields = ['name', 'template_type', 'subject', 'body', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': TEXT, 'placeholder': 'e.g. Sycamore 2026 — Welcome'}),
            'template_type': forms.Select(attrs={'class': SELECT}),
            'subject': forms.TextInput(attrs={'class': TEXT, 'placeholder': 'e.g. Welcome to {{ event_title }}, {{ first_name }}!'}),
            'body': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 12, 'placeholder': 'Dear {{ first_name }},\n\n…'}),
        }


class EmailCampaignForm(forms.ModelForm):
    target_category = forms.ChoiceField(
        required=False, label='Category',
        choices=[('', 'Everyone')] + list(RegistrationCategory.choices),
        widget=forms.Select(attrs={'class': SELECT}),
    )
    target_worker_type = forms.ChoiceField(
        required=False, label='Worker type',
        choices=[('', 'Any')] + list(WorkerType.choices),
        widget=forms.Select(attrs={'class': SELECT}),
    )

    class Meta:
        model = EmailCampaign
        fields = [
            'name', 'template', 'event',
            'target_category', 'target_worker_type', 'target_department',
            'target_state', 'target_country', 'target_church_name', 'target_returning',
            'scheduled_at',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': TEXT, 'placeholder': 'e.g. Sycamore 2026 Reminder — Week Of'}),
            'template': forms.Select(attrs={'class': SELECT}),
            'event': forms.Select(attrs={'class': SELECT}),
            'target_department': forms.Select(attrs={'class': SELECT}),
            'target_state': forms.TextInput(attrs={'class': TEXT, 'placeholder': 'e.g. Lagos'}),
            'target_country': forms.TextInput(attrs={'class': TEXT, 'placeholder': 'e.g. Nigeria'}),
            'target_church_name': forms.TextInput(attrs={'class': TEXT, 'placeholder': 'e.g. Sycamore'}),
            'target_returning': forms.Select(attrs={'class': SELECT}),
            'scheduled_at': forms.DateTimeInput(attrs={'class': TEXT, 'type': 'datetime-local'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['template'].queryset = EmailTemplate.objects.filter(is_active=True)
        self.fields['event'].queryset = Event.objects.exclude(status=EventStatus.ARCHIVED).order_by('-year')
        self.fields['event'].required = False
        self.fields['event'].empty_label = 'All events'
        self.fields['target_department'].queryset = Department.objects.filter(is_active=True)
        self.fields['target_department'].required = False
        self.fields['target_department'].empty_label = 'Any department'
        self.fields['scheduled_at'].required = False
