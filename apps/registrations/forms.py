"""
Forms backing the registration wizard (apps/registrations/views.py).

The wizard mirrors the spec's flow exactly:

    Have you attended any previous Sycamore Conference?
        NO  -> StartForm -> PersonForm (blank)          -> RegistrationDetailsForm -> confirm
        YES -> StartForm -> PersonSearchForm -> (match)  -> PersonForm (prefilled)  -> RegistrationDetailsForm -> confirm
"""

from django import forms

from apps.departments.models import Department
from apps.events.models import Event, EventStatus
from apps.people.models import Person
from apps.registrations.models import Registration, RegistrationCategory, WorkerType

TEXT_INPUT = 'field-input'
TEXTAREA = 'field-input field-textarea'
SELECT = 'field-input field-select'


class StartForm(forms.Form):
    """Step 1: which event, and has this person attended before."""

    ATTENDED_CHOICES = [
        ('no', "No — this is their first Sycamore conference"),
        ('yes', 'Yes — they have attended a previous conference'),
    ]

    event = forms.ModelChoiceField(
        queryset=Event.objects.exclude(status=EventStatus.ARCHIVED).order_by('-year'),
        empty_label='Select an event…',
        widget=forms.Select(attrs={'class': SELECT}),
    )
    attended_before = forms.ChoiceField(
        choices=ATTENDED_CHOICES,
        widget=forms.RadioSelect,
        label='Have you attended any previous Sycamore Conference?',
    )


class PersonSearchForm(forms.Form):
    """Step 2 (returning-attendee branch): look an existing Person up."""

    phone_number = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': TEXT_INPUT, 'placeholder': 'e.g. 08012345678'}))
    email_address = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': TEXT_INPUT, 'placeholder': 'name@example.com'}))
    person_id = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': TEXT_INPUT, 'placeholder': 'SYC-000123'}))
    qr_token = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': TEXT_INPUT, 'placeholder': 'Scan or paste QR value'}))

    def clean(self):
        cleaned = super().clean()
        if not any(cleaned.get(f) for f in ('phone_number', 'email_address', 'person_id', 'qr_token')):
            raise forms.ValidationError('Enter at least one detail to search by (phone, email, Person ID, or QR code).')
        return cleaned


class PersonForm(forms.ModelForm):
    """Step 3: the Person record itself — blank for a first-timer, pre-filled
    (and editable) for a returning attendee."""

    class Meta:
        model = Person
        fields = [
            'photo',
            'first_name', 'middle_name', 'last_name',
            'gender', 'date_of_birth', 'marital_status',
            'phone_number', 'alternative_phone', 'email_address',
            'residential_address', 'state', 'local_government', 'country',
            'church_name', 'church_address', 'pastors_name',
            'occupation',
            'emergency_contact_name', 'emergency_phone', 'emergency_relationship',
            'medical_notes', 'dietary_notes',
        ]
        widgets = {
            'photo': forms.ClearableFileInput(attrs={'class': 'field-file'}),
            'first_name': forms.TextInput(attrs={'class': TEXT_INPUT}),
            'middle_name': forms.TextInput(attrs={'class': TEXT_INPUT}),
            'last_name': forms.TextInput(attrs={'class': TEXT_INPUT}),
            'gender': forms.Select(attrs={'class': SELECT}),
            'date_of_birth': forms.DateInput(attrs={'class': TEXT_INPUT, 'type': 'date'}),
            'marital_status': forms.Select(attrs={'class': SELECT}),
            'phone_number': forms.TextInput(attrs={'class': TEXT_INPUT}),
            'alternative_phone': forms.TextInput(attrs={'class': TEXT_INPUT}),
            'email_address': forms.EmailInput(attrs={'class': TEXT_INPUT}),
            'residential_address': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 2}),
            'state': forms.TextInput(attrs={'class': TEXT_INPUT}),
            'local_government': forms.TextInput(attrs={'class': TEXT_INPUT}),
            'country': forms.TextInput(attrs={'class': TEXT_INPUT}),
            'church_name': forms.TextInput(attrs={'class': TEXT_INPUT}),
            'church_address': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 2}),
            'pastors_name': forms.TextInput(attrs={'class': TEXT_INPUT}),
            'occupation': forms.TextInput(attrs={'class': TEXT_INPUT}),
            'emergency_contact_name': forms.TextInput(attrs={'class': TEXT_INPUT}),
            'emergency_phone': forms.TextInput(attrs={'class': TEXT_INPUT}),
            'emergency_relationship': forms.TextInput(attrs={'class': TEXT_INPUT}),
            'medical_notes': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 2}),
            'dietary_notes': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
        self.fields['phone_number'].required = True


class RegistrationDetailsForm(forms.ModelForm):
    """Step 3 (continued, same page as PersonForm): what they're
    registering as for this specific event."""

    class Meta:
        model = Registration
        fields = ['category', 'worker_type', 'department', 'accommodation_requested']
        widgets = {
            'category': forms.RadioSelect,
            'worker_type': forms.Select(attrs={'class': SELECT}),
            'department': forms.Select(attrs={'class': SELECT}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['department'].queryset = Department.objects.filter(is_active=True)
        self.fields['department'].required = False
        self.fields['department'].empty_label = 'Select department…'
        # worker_type is a plain ChoiceField (model field has choices=), not a
        # ModelChoiceField, so it has no empty_label — swap in a friendlier
        # blank option than Django's default '---------' instead.
        self.fields['worker_type'].required = False
        self.fields['worker_type'].choices = [('', 'Select worker type…')] + list(WorkerType.choices)

    def clean(self):
        cleaned = super().clean()
        category = cleaned.get('category')
        worker_type = cleaned.get('worker_type')
        department = cleaned.get('department')

        if category == RegistrationCategory.WORKER:
            if not worker_type:
                self.add_error('worker_type', 'Worker type (Member/Pastor) is required for worker registrations.')
            if not department:
                self.add_error('department', 'Workers must be assigned to a department.')
        elif category == RegistrationCategory.PARTICIPANT and worker_type:
            self.add_error('worker_type', 'Participants should not have a worker type — leave this blank.')

        return cleaned
