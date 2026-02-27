from django import forms
from .models import IFMISResetRequest, IFMISRequestMessage

class IFMISResetForm(forms.ModelForm):
    class Meta:
        model = IFMISResetRequest
        fields = ['full_name', 'department', 'email', 'uploaded_file']


class IFMISRequestMessageForm(forms.ModelForm):
    class Meta:
        model = IFMISRequestMessage
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'rows':2, 'placeholder':'Type your message...'})
        }