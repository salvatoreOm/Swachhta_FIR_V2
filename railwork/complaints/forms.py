from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Complaint, ComplaintPhoto, OTPVerification, Station, PlatformLocation

class ComplaintPhotoForm(forms.ModelForm):
    class Meta:
        model = ComplaintPhoto
        fields = ['photo']

class ComplaintForm(forms.ModelForm):
    class Meta:
        model = Complaint
        fields = ['station', 'platform_location', 'description', 'reporter_name', 'reporter_phone']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': _('Describe the cleanliness issue')}),
            'reporter_name': forms.TextInput(attrs={'placeholder': _('Your name')}),
            'reporter_phone': forms.TextInput(attrs={'placeholder': _('Your phone number for OTP verification')}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Make description and reporter_name optional
        self.fields['description'].required = False
        self.fields['reporter_name'].required = False
        
        # Update field labels - add * for required fields, clean labels for optional
        self.fields['station'].label = _('Station*')
        self.fields['platform_location'].label = _('Platform Location')
        self.fields['description'].label = _('Issue Description')
        self.fields['reporter_name'].label = _('Reporter Name')
        self.fields['reporter_phone'].label = _('Phone Number*')
        
        # If initial station is provided, filter platform_locations
        if 'initial' in kwargs and 'station' in kwargs['initial']:
            station = kwargs['initial']['station']
            self.fields['platform_location'].queryset = station.platform_locations.all()
            self.fields['platform_location'].empty_label = _('Select Platform Location')
        else:
            # If no station provided, show all platform locations but with helpful empty label
            self.fields['platform_location'].queryset = PlatformLocation.objects.all()
            self.fields['platform_location'].empty_label = _('Please scan QR code or select station first')

class OTPVerificationForm(forms.ModelForm):
    class Meta:
        model = OTPVerification
        fields = ['otp']
        widgets = {
            'otp': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Enter OTP')}),
        } 