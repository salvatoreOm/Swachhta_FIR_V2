from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Complaint, ComplaintPhoto

class ComplaintPhotoForm(forms.ModelForm):
    class Meta:
        model = ComplaintPhoto
        fields = ['photo']

class ComplaintForm(forms.ModelForm):
    photo_1 = forms.ImageField(
        label=_('Photo 1'),
        required=True,
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )
    photo_2 = forms.ImageField(
        label=_('Photo 2'),
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )
    photo_3 = forms.ImageField(
        label=_('Photo 3'),
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )
    photo_4 = forms.ImageField(
        label=_('Photo 4'),
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Complaint
        fields = ['description', 'location_details', 'reporter_name', 'reporter_phone']
        widgets = {
            'description': forms.Textarea(attrs={
                'rows': 4,
                'class': 'form-control',
                'placeholder': _('Describe the cleanliness issue')
            }),
            'location_details': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': _('Provide specific location details within the platform')
            }),
            'reporter_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Your Name')
            }),
            'reporter_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'type': 'tel',
                'placeholder': _('Your Phone Number')
            }),
        }
        help_texts = {
            'description': _('Please provide details about the cleanliness issue'),
            'location_details': _('Example: Near platform entrance, beside bench, etc.'),
            'reporter_phone': _('We will send an OTP to this number for verification'),
        }

class OTPVerificationForm(forms.Form):
    otp = forms.CharField(
        label=_('OTP'),
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Enter 6-digit OTP')
        })
    ) 