from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Complaint, ComplaintPhoto, OTPVerification

class ComplaintPhotoForm(forms.ModelForm):
    class Meta:
        model = ComplaintPhoto
        fields = ['photo']

class ComplaintForm(forms.ModelForm):
    class Meta:
        model = Complaint
        fields = ['station', 'platform_location', 'description', 'reporter_name', 'reporter_phone']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # If initial station is provided, filter platform_locations
        if 'initial' in kwargs and 'station' in kwargs['initial']:
            station = kwargs['initial']['station']
            self.fields['platform_location'].queryset = station.platform_locations.all()
        else:
            self.fields['platform_location'].queryset = self.fields['platform_location'].queryset.none()

class OTPVerificationForm(forms.ModelForm):
    class Meta:
        model = OTPVerification
        fields = ['otp']
        widgets = {
            'otp': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Enter OTP')}),
        } 