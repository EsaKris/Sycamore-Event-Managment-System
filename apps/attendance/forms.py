from django import forms

from apps.events.models import Event, EventStatus

from .models import AttendanceSession, SessionType

TEXT_INPUT = 'field-input'
SELECT = 'field-input field-select'


class EventPickerForm(forms.Form):
    """Standalone event selector used at the top of both the scanner and
    the attendance log — kept separate from SessionCreateForm since an
    event can be picked without necessarily creating a new session."""

    event = forms.ModelChoiceField(
        queryset=Event.objects.exclude(status=EventStatus.ARCHIVED).order_by('-year'),
        empty_label='Select an event…',
        widget=forms.Select(attrs={'class': SELECT}),
    )


class SessionCreateForm(forms.ModelForm):
    class Meta:
        model = AttendanceSession
        fields = ['label', 'session_type', 'date']
        widgets = {
            'label': forms.TextInput(attrs={'class': TEXT_INPUT, 'placeholder': "e.g. Day 1 - Morning Service"}),
            'session_type': forms.Select(attrs={'class': SELECT}),
            'date': forms.DateInput(attrs={'class': TEXT_INPUT, 'type': 'date'}),
        }

    def __init__(self, *args, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._event = event
        if not self.initial.get('session_type'):
            self.initial['session_type'] = SessionType.CUSTOM

    def save(self, commit=True):
        session = super().save(commit=False)
        session.event = self._event
        if commit:
            session.save()
        return session
