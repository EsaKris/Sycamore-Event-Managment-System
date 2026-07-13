from django import forms

from .models import AdminRole

TEXT_INPUT = 'field-input'
SELECT = 'field-input field-select'


class PersonSearchForm(forms.Form):
    q = forms.CharField(
        required=False, label='',
        widget=forms.TextInput(attrs={'class': TEXT_INPUT, 'placeholder': 'Search by name, phone, email, or Person ID…'}),
    )


class MakeAdministratorForm(forms.Form):
    role = forms.ChoiceField(choices=AdminRole.choices, widget=forms.Select(attrs={'class': SELECT}))


class ChangeRoleForm(forms.Form):
    role = forms.ChoiceField(choices=AdminRole.choices, widget=forms.Select(attrs={'class': SELECT}))
