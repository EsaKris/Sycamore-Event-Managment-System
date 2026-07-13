from django import forms

from apps.accounts.models import User
from apps.events.models import Event, EventStatus

from .models import FollowUp, FollowUpOutcome, FollowUpStatus

TEXT = 'field-input'
SELECT = 'field-input field-select'
TEXTAREA = 'field-input field-textarea'


class PersonLookupForm(forms.Form):
    """'Find a Person' — the entry point into the follow-up module, mirroring
    the same phone/email/Person ID/QR pattern used by the registration
    search step for a consistent front-desk experience."""

    identifier = forms.CharField(
        label='Phone, email, Person ID, or QR code',
        widget=forms.TextInput(attrs={'class': TEXT, 'placeholder': 'e.g. 08012345678 or SYC-000123'}),
    )


class FollowUpForm(forms.ModelForm):
    """Logs one new timeline entry for a Person."""

    class Meta:
        model = FollowUp
        fields = [
            'event', 'follow_up_type', 'interest_level', 'remarks',
            'outcome', 'status', 'next_follow_up_date', 'officer_assigned',
        ]
        widgets = {
            'event': forms.Select(attrs={'class': SELECT}),
            'follow_up_type': forms.Select(attrs={'class': SELECT}),
            'interest_level': forms.Select(attrs={'class': SELECT}),
            'remarks': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 3, 'placeholder': 'What was discussed / next steps…'}),
            'outcome': forms.Select(attrs={'class': SELECT}),
            'status': forms.Select(attrs={'class': SELECT}),
            'next_follow_up_date': forms.DateInput(attrs={'class': TEXT, 'type': 'date'}),
            'officer_assigned': forms.Select(attrs={'class': SELECT}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['event'].queryset = Event.objects.exclude(status=EventStatus.ARCHIVED).order_by('-year')
        self.fields['event'].required = False
        self.fields['event'].empty_label = 'Not tied to a specific event'
        self.fields['officer_assigned'].queryset = User.objects.filter(is_active_administrator=True).order_by('first_name')
        self.fields['officer_assigned'].required = False
        self.fields['officer_assigned'].empty_label = 'Unassigned'


class FollowUpQuickCloseForm(forms.Form):
    """Used for the one-click 'Close' action from the list/timeline."""

    outcome = forms.ChoiceField(choices=FollowUpOutcome.choices, widget=forms.Select(attrs={'class': SELECT}))
