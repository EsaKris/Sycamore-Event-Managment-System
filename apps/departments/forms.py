from django import forms

from .models import Department


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'field-input', 'placeholder': 'e.g. Media, Ushering, Choir'}),
            'description': forms.Textarea(attrs={'class': 'field-input', 'rows': 3}),
        }
