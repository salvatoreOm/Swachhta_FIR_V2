from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _

class Station(models.Model):
    name = models.CharField(_('Station Name'), max_length=100)
    station_code = models.CharField(_('Station Code'), max_length=10, unique=True)
    
    def __str__(self):
        return f"{self.name} ({self.station_code})"

    class Meta:
        verbose_name = _('Station')
        verbose_name_plural = _('Stations')

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
    platform_number = models.IntegerField(_('Platform Number'), validators=[MinValueValidator(1)])
    description = models.TextField(_('Issue Description'))
    location_details = models.TextField(_('Location Details'), help_text=_('Specific location details within the platform'), null=True, blank=True)
    reporter_name = models.CharField(_('Reporter Name'), max_length=100)
    reporter_phone = models.CharField(_('Phone Number'), max_length=15)
    status = models.CharField(_('Status'), max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    complaint_number = models.CharField(_('Complaint Number'), max_length=20, unique=True, editable=False)
    is_verified = models.BooleanField(_('Is Verified'), default=False)

    def save(self, *args, **kwargs):
        if not self.complaint_number:
            # Generate a unique complaint number: YYYYMMDD-STATION-XXXX
            date_str = timezone.now().strftime('%Y%m%d')
            count = Complaint.objects.filter(created_at__date=timezone.now().date()).count() + 1
            self.complaint_number = f"{date_str}-{self.station.station_code}-{count:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Complaint {self.complaint_number} - {self.station.name} Platform {self.platform_number}"

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
