from django import forms
import mimetypes
import os

from .models import IFMISResetRequest, IFMISRequestMessage

class IFMISResetForm(forms.ModelForm):
    MAX_UPLOAD_SIZE = 5 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png'}
    ALLOWED_CONTENT_TYPES = {'application/pdf', 'image/jpeg', 'image/png'}

    class Meta:
        model = IFMISResetRequest
        fields = ['full_name', 'department', 'email', 'uploaded_file']

    def clean_uploaded_file(self):
        uploaded_file = self.cleaned_data.get('uploaded_file')
        if not uploaded_file:
            return uploaded_file

        if uploaded_file.size > self.MAX_UPLOAD_SIZE:
            raise forms.ValidationError("File size must be 5MB or less.")

        extension = os.path.splitext(uploaded_file.name)[1].lower()
        if extension not in self.ALLOWED_EXTENSIONS:
            raise forms.ValidationError("Only PDF, JPG, and PNG files are allowed.")

        content_type = getattr(uploaded_file, 'content_type', None) or mimetypes.guess_type(uploaded_file.name)[0]
        if content_type and content_type.lower() not in self.ALLOWED_CONTENT_TYPES:
            raise forms.ValidationError("Unsupported file type. Please upload PDF, JPG, or PNG.")

        return uploaded_file


class IFMISRequestMessageForm(forms.ModelForm):
    class Meta:
        model = IFMISRequestMessage
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'rows':2, 'placeholder':'Type your message...'})
        }
