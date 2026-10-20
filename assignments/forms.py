from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()


class AssignStudentsForm(forms.Form):
    student_ids = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(role='student').order_by('name'),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        error_messages={'required': 'Please select at least one student to assign.'}
    )
