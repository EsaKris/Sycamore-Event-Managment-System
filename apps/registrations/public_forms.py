from django import forms

from apps.people.models import Gender, MaritalStatus

TEXT = 'w-full rounded-lg bg-[#12161F] border border-[#212836] px-4 py-3 text-sm text-[#EDEFF3] placeholder:text-[#6B7386] focus:outline-none focus:border-[#D4A24C] transition-colors'
SELECT = TEXT + ' appearance-none'


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
        widget=forms.RadioSelect, initial='no',
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
        return data
