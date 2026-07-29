from django import forms

from apps.departments.models import Department
from apps.people.models import Gender, MaritalStatus
from apps.registrations.models import WorkerType

TEXT = 'w-full rounded-lg bg-[#12161F] border border-[#212836] px-4 py-3 text-sm text-[#EDEFF3] placeholder:text-[#6B7386] focus:outline-none focus:border-[#D4A24C] transition-colors'
SELECT = TEXT + ' appearance-none'
FILE = 'w-full rounded-lg bg-[#12161F] border border-[#212836] px-4 py-3 text-sm text-[#EDEFF3] file:mr-3 file:rounded-md file:border-0 file:bg-[#D4A24C] file:text-[#1a1305] file:font-semibold file:px-3 file:py-1.5 file:text-xs focus:outline-none focus:border-[#D4A24C] transition-colors'


class PublicRegistrationForm(forms.Form):
    """
    Deliberately a plain Form, not a ModelForm — Person creation/updates
    are owned by PersonService (via RegistrationService.register_public),
    never a direct .save(). Field set is a public-appropriate subset of
    Person: no medical/emergency-contact fields here, those are collected
    by staff at check-in if actually needed, not asked of a stranger
    filling out a web form.
    """

    # "Have you attended before?" — a real, visible question again (not just the
    # invisible server-side match RegistrationService.register_public() already
    # does on submit). Answering 'yes' drives the client-side quick-check step in
    # register.html, which looks the visitor up by the phone number *they just
    # typed* via check_returning() and pre-fills the rest of the form — never a
    # browsable search, so it can't surface anyone else's details. This field
    # itself has no server-side branching; the actual dedup/match happens the
    # same way regardless of the answer given here.
    has_attended_before = forms.ChoiceField(
        choices=[('no', "No, this is my first time"), ('yes', 'Yes, I have attended before')],
        widget=forms.HiddenInput, initial='no',
    )

    photo = forms.ImageField(
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': FILE, 'accept': 'image/*'}),
        help_text='Passport photograph for your ID card (optional).',
    )
    first_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': TEXT, 'placeholder': 'First name'}))
    last_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': TEXT, 'placeholder': 'Last name'}))
    gender = forms.ChoiceField(choices=Gender.choices, widget=forms.Select(attrs={'class': SELECT}))
    phone_number = forms.CharField(max_length=20, widget=forms.TextInput(attrs={'class': TEXT, 'placeholder': '+234...'}))
    email_address = forms.EmailField(required=False, widget=forms.EmailInput(attrs={'class': TEXT, 'placeholder': 'you@example.com (optional)'}))
    date_of_birth = forms.DateField(required=False, widget=forms.DateInput(attrs={'class': TEXT, 'type': 'date'}))
    marital_status = forms.ChoiceField(choices=[('', '—')] + list(MaritalStatus.choices), required=False, widget=forms.Select(attrs={'class': SELECT}))
    state = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={'class': TEXT, 'placeholder': 'State'}))
    country = forms.CharField(max_length=100, required=False, initial='Nigeria', widget=forms.TextInput(attrs={'class': TEXT}))
    church_name = forms.CharField(max_length=255, required=False, widget=forms.TextInput(attrs={'class': TEXT, 'placeholder': 'Your home church (optional)'}))
    occupation = forms.CharField(max_length=255, required=False, widget=forms.TextInput(attrs={'class': TEXT, 'placeholder': 'Optional'}))
    accommodation_requested = forms.BooleanField(required=False, label='I need accommodation during the conference')

    # Honeypot — real visitors never see or fill this (hidden via CSS in the template);
    # bots that blindly fill every field trip it.
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'autocomplete': 'off', 'tabindex': '-1',
    }))

    def clean_website(self):
        value = self.cleaned_data.get('website', '')
        if value:
            raise forms.ValidationError('Spam detected.')
        return value

    def person_fields(self) -> dict:
        excluded = ('website', 'accommodation_requested', 'has_attended_before')
        data = {k: v for k, v in self.cleaned_data.items() if k not in excluded}
        data['country'] = data.get('country') or 'Nigeria'
        # An empty upload means "didn't choose a new file" here, same as
        # ClearableFileInput elsewhere — never overwrite an existing photo
        # with nothing just because a returning visitor left it untouched.
        if not data.get('photo'):
            data.pop('photo', None)
        return data


class WorkerPublicRegistrationForm(forms.Form):
    """
    The public self-registration form for Workers and Pastors — a
    lighter-weight sibling of PublicRegistrationForm. Per spec this
    collects only what's needed to get a worker/pastor onto their
    department roster and printed an ID card: name, contact details,
    date of birth, department, and a passport photo. Deliberately a
    plain Form for the same reason as PublicRegistrationForm — Person/
    Registration creation is owned by RegistrationService, never a
    direct .save() here.
    """

    has_attended_before = forms.ChoiceField(
        choices=[('no', "No, this is my first time"), ('yes', 'Yes, I have attended before')],
        widget=forms.HiddenInput, initial='no',
    )

    photo = forms.ImageField(
        required=True,
        widget=forms.ClearableFileInput(attrs={'class': FILE, 'accept': 'image/*'}),
        help_text='A clear, recent passport photograph for your ID card.',
    )
    first_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': TEXT, 'placeholder': 'First name'}))
    last_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': TEXT, 'placeholder': 'Last name'}))
    gender = forms.ChoiceField(choices=Gender.choices, widget=forms.Select(attrs={'class': SELECT}))
    date_of_birth = forms.DateField(required=True, widget=forms.DateInput(attrs={'class': TEXT, 'type': 'date'}))
    phone_number = forms.CharField(max_length=20, widget=forms.TextInput(attrs={'class': TEXT, 'placeholder': '+234...'}))
    email_address = forms.EmailField(required=False, widget=forms.EmailInput(attrs={'class': TEXT, 'placeholder': 'you@example.com (optional)'}))

    worker_type = forms.ChoiceField(
        choices=WorkerType.choices,
        widget=forms.Select(attrs={'class': SELECT}),
        label='Are you registering as a Worker or a Pastor?',
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.filter(is_active=True),
        empty_label='Select department…',
        widget=forms.Select(attrs={'class': SELECT}),
    )
    church_name = forms.CharField(max_length=255, required=False, widget=forms.TextInput(attrs={'class': TEXT, 'placeholder': 'Your home church (optional)'}))

    # Honeypot, same pattern as PublicRegistrationForm.
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'autocomplete': 'off', 'tabindex': '-1',
    }))

    def clean_website(self):
        value = self.cleaned_data.get('website', '')
        if value:
            raise forms.ValidationError('Spam detected.')
        return value

    def person_fields(self) -> dict:
        excluded = ('website', 'has_attended_before', 'worker_type', 'department')
        data = {k: v for k, v in self.cleaned_data.items() if k not in excluded}
        data['country'] = 'Nigeria'
        if not data.get('photo'):
            data.pop('photo', None)
        return data

    def registration_fields(self) -> dict:
        return {
            'category': 'worker',
            'worker_type': self.cleaned_data['worker_type'],
            'department': self.cleaned_data['department'],
        }
