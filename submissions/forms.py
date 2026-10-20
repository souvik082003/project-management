from django import forms


class SubmissionForm(forms.Form):
    file = forms.FileField(
        required=True,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'id': 'submissionFileInput',
            'accept': '.pdf,.doc,.docx,.zip,.ppt,.pptx,.txt,.png,.jpg'
        }),
        help_text="Allowed formats: PDF, DOC, DOCX, ZIP, PPT, PPTX, TXT, PNG, JPG (Max 10 MB)."
    )
