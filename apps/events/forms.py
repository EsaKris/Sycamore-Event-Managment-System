from django import forms

from .models import Event, EventStatus

TEXT_INPUT = 'field-input'
SELECT = 'field-input field-select'


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            'title', 'theme', 'description', 'year', 'venue', 'banner', 'logo',
            'start_date', 'end_date', 'max_capacity', 'color_theme', 'status',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': TEXT_INPUT, 'placeholder': 'e.g. Sycamore 2027'}),
            'theme': forms.TextInput(attrs={'class': TEXT_INPUT, 'placeholder': 'Conference theme'}),
            'description': forms.Textarea(attrs={'class': TEXT_INPUT, 'rows': 4}),
            'year': forms.NumberInput(attrs={'class': TEXT_INPUT}),
            'venue': forms.TextInput(attrs={'class': TEXT_INPUT}),
            'start_date': forms.DateInput(attrs={'class': TEXT_INPUT, 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': TEXT_INPUT, 'type': 'date'}),
            'max_capacity': forms.NumberInput(attrs={'class': TEXT_INPUT, 'placeholder': 'Leave blank for unlimited'}),
            'color_theme': forms.TextInput(attrs={'class': TEXT_INPUT, 'placeholder': '#D4A24C'}),
            'status': forms.Select(attrs={'class': SELECT}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['status'].initial = EventStatus.DRAFT

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get('start_date'), cleaned.get('end_date')
        if start and end and end < start:
            self.add_error('end_date', 'End date cannot be before start date.')
        return cleaned
