from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User
import qrcode
from io import BytesIO
from django.core.files import File
from PIL import Image
import os

class City(models.Model):
    name = models.CharField(_('City Name'), max_length=100)
    code = models.CharField(_('City Code'), max_length=10, unique=True)
    admin = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='administered_cities')
    
    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _('City')
        verbose_name_plural = _('Cities')

class LocationType(models.Model):
    name = models.CharField(_('Location Type'), max_length=100)
    
    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _('Location Type')
        verbose_name_plural = _('Location Types')

class Station(models.Model):
    name = models.CharField(_('Station Name'), max_length=100)
    station_code = models.CharField(_('Station Code'), max_length=10)
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='stations', null=True, blank=True)
    total_platforms = models.IntegerField(_('Total Platforms'), validators=[MinValueValidator(1)], default=1)
    
    def __str__(self):
        return f"{self.name} ({self.station_code})"

    class Meta:
        verbose_name = _('Station')
        verbose_name_plural = _('Stations')
        unique_together = ['station_code', 'city']  # Station codes are unique within a city

class PlatformLocation(models.Model):
    station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name='platform_locations')
    platform_number = models.IntegerField(_('Platform Number'), validators=[MinValueValidator(1)])
    location_type = models.ForeignKey(LocationType, on_delete=models.CASCADE)
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True, null=True)
    
    def generate_qr_code(self):
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        
        # Generate URL for the complaint form with station and platform info
        data = f"https://{os.getenv('DOMAIN', 'localhost:8000')}/submit-complaint/?station={self.station.id}&platform={self.platform_number}&location={self.location_type.id}"
        qr.add_data(data)
        qr.make(fit=True)

        qr_image = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to RGB if necessary
        if qr_image.mode != 'RGB':
            qr_image = qr_image.convert('RGB')
        
        # Save QR code
        buffer = BytesIO()
        qr_image.save(buffer, format='PNG')
        filename = f'qr_station_{self.station.station_code}_platform_{self.platform_number}_{self.location_type.name}.png'
        self.qr_code.save(filename, File(buffer), save=False)
        
    def save(self, *args, **kwargs):
        if not self.qr_code:
            self.generate_qr_code()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.station.name} - Platform {self.platform_number} - {self.location_type.name}"

    class Meta:
        verbose_name = _('Platform Location')
        verbose_name_plural = _('Platform Locations')
        unique_together = ['station', 'platform_number', 'location_type']

class ComplaintPhoto(models.Model):
    complaint = models.ForeignKey('Complaint', on_delete=models.CASCADE, related_name='photos')
    photo = models.ImageField(upload_to='complaints/photos/')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Complaint Photo')
        verbose_name_plural = _('Complaint Photos')

class Complaint(models.Model):
    STATUS_CHOICES = [
        ('PENDING', _('Pending')),
        ('IN_PROGRESS', _('In Progress')),
        ('RESOLVED', _('Resolved')),
        ('CLOSED', _('Closed')),
    ]
    
    station = models.ForeignKey(Station, on_delete=models.CASCADE, verbose_name=_('Station'))
    platform_location = models.ForeignKey(PlatformLocation, on_delete=models.CASCADE, verbose_name=_('Platform Location'), null=True, blank=True)
    description = models.TextField(_('Issue Description'))
    reporter_name = models.CharField(_('Reporter Name'), max_length=100)
    reporter_phone = models.CharField(_('Phone Number'), max_length=15)
    status = models.CharField(_('Status'), max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    complaint_number = models.CharField(_('Complaint Number'), max_length=20, unique=True, editable=False)
    is_verified = models.BooleanField(_('Is Verified'), default=False)
    assigned_worker = models.CharField(_('Assigned Worker'), max_length=100, blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.complaint_number:
            # Generate a unique complaint number: YYYYMMDD-CITY-STATION-XXXX
            date_str = timezone.now().strftime('%Y%m%d')
            count = Complaint.objects.filter(
                created_at__date=timezone.now().date(),
                station__city=self.station.city
            ).count() + 1
            self.complaint_number = f"{date_str}-{self.station.city.code}-{self.station.station_code}-{count:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        platform_info = f" Platform {self.platform_location.platform_number}" if self.platform_location else ""
        return f"Complaint {self.complaint_number} - {self.station.name}{platform_info}"

    class Meta:
        verbose_name = _('Complaint')
        verbose_name_plural = _('Complaints')

class OTPVerification(models.Model):
    complaint = models.OneToOneField(Complaint, on_delete=models.CASCADE, verbose_name=_('Complaint'))
    otp = models.CharField(_('OTP'), max_length=6)
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    is_verified = models.BooleanField(_('Is Verified'), default=False)
    attempts = models.IntegerField(_('Attempts'), default=0)

    def __str__(self):
        return f"OTP for {self.complaint.complaint_number}"

    class Meta:
        verbose_name = _('OTP Verification')
        verbose_name_plural = _('OTP Verifications')
