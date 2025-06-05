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

class UserProfile(models.Model):
    """Extended user profile to manage station-specific permissions"""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    station = models.OneToOneField('Station', on_delete=models.CASCADE, null=True, blank=True)
    can_manage_station = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.station.name if self.station else 'No Station'}"
    
    class Meta:
        verbose_name = _('User Profile')
        verbose_name_plural = _('User Profiles')

class City(models.Model):
    name = models.CharField(_('City Name'), max_length=100)
    code = models.CharField(_('City Code'), max_length=10, unique=True)
    admin = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='administered_cities')
    
    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _('City')
        verbose_name_plural = _('Cities')

# Keep LocationType for backward compatibility but mark as deprecated
class LocationType(models.Model):
    name = models.CharField(_('Location Type'), max_length=100)
    
    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _('Location Type (Deprecated)')
        verbose_name_plural = _('Location Types (Deprecated)')

class Station(models.Model):
    name = models.CharField(_('Station Name'), max_length=100)
    station_code = models.CharField(_('Station Code'), max_length=10)
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='stations', null=True, blank=True)
    total_platforms = models.IntegerField(_('Total Platforms'), validators=[MinValueValidator(1)], default=1)
    manager = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_station')
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    
    def __str__(self):
        return f"{self.name} ({self.station_code})"

    class Meta:
        verbose_name = _('Station')
        verbose_name_plural = _('Stations')
        unique_together = ['station_code', 'city']  # Station codes are unique within a city

class PlatformLocation(models.Model):
    station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name='platform_locations')
    platform_number = models.IntegerField(_('Platform Number'), validators=[MinValueValidator(1)])
    # Replace location_type with custom location description
    location_type = models.ForeignKey(LocationType, on_delete=models.CASCADE, null=True, blank=True)  # Keep for backward compatibility
    location_description = models.CharField(_('Location Description'), max_length=200, default='General Area', help_text=_('Custom description of the location (e.g., "Near Ticket Counter", "Platform Entry", "Waiting Area")'))
    hash_id = models.CharField(_('Hash ID'), max_length=15, blank=True, help_text=_('Format: (Platform Number/QR Number) (e.g., (1/1), (1/2), (2/1))'))
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    
    def generate_hash_id(self):
        """Generate hash_id in format (Platform Number/QR Number)"""
        # Count existing locations for this platform
        existing_count = PlatformLocation.objects.filter(
            station=self.station,
            platform_number=self.platform_number
        ).exclude(pk=self.pk).count()
        
        # Sequence number is existing_count + 1
        sequence = existing_count + 1
        
        # Format: (Platform Number/QR Number)
        self.hash_id = f"({self.platform_number}/{sequence})"
    
    def generate_qr_code(self):
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        
        # Fix: Use HTTP instead of HTTPS for development, and ensure we have an ID
        protocol = 'http'  # Changed from https to http for development
        domain = os.getenv('DOMAIN', 'localhost:8000')
        
        # Generate URL for the complaint form with station and platform info
        # Include language prefix to match Django's i18n URL structure
        data = f"{protocol}://{domain}/en/submit-complaint/?station={self.station.id}&platform={self.platform_number}&location={self.id}"
        qr.add_data(data)
        qr.make(fit=True)

        qr_image = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to RGB if necessary
        if qr_image.mode != 'RGB':
            qr_image = qr_image.convert('RGB')
        
        # Save QR code
        buffer = BytesIO()
        qr_image.save(buffer, format='PNG')
        # Use location description instead of location_type.name
        location_name = self.location_description.replace(' ', '_').replace(',', '').replace('/', '_')
        filename = f'qr_station_{self.station.station_code}_platform_{self.platform_number}_{location_name}_{self.id}.png'
        self.qr_code.save(filename, File(buffer), save=False)
        
    def save(self, *args, **kwargs):
        # Generate hash_id if it doesn't exist
        if not self.hash_id:
            # We need to call this after super().save() to ensure we have a pk for exclusion
            pass
        
        # First save to get an ID
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Generate hash_id if it wasn't set
        if not self.hash_id:
            self.generate_hash_id()
            # Save again to update the hash_id field
            super().save(update_fields=['hash_id'])
        
        # Then generate QR code if it's a new object or QR code doesn't exist
        if is_new or not self.qr_code:
            self.generate_qr_code()
            # Save again to update the qr_code field
            super().save(update_fields=['qr_code'])

    def __str__(self):
        return f"{self.station.name} - Platform {self.platform_number} - {self.location_description}"

    class Meta:
        verbose_name = _('Platform Location')
        verbose_name_plural = _('Platform Locations')
        unique_together = ['station', 'platform_number', 'location_description']

class ComplaintPhoto(models.Model):
    complaint = models.ForeignKey('Complaint', on_delete=models.CASCADE, related_name='photos')
    photo = models.ImageField(upload_to='complaints/photos/')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Complaint Photo')
        verbose_name_plural = _('Complaint Photos')

class QRScanAttempt(models.Model):
    """Track duplicate QR scan attempts for the same location within 15-minute windows"""
    platform_location = models.ForeignKey(PlatformLocation, on_delete=models.CASCADE, related_name='scan_attempts')
    original_complaint = models.ForeignKey('Complaint', on_delete=models.CASCADE, related_name='duplicate_scan_attempts')
    attempt_count = models.IntegerField(_('Attempt Count'), default=1, help_text=_('Number of duplicate scan attempts'))
    last_attempt_at = models.DateTimeField(_('Last Attempt At'), auto_now=True)
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    
    # Optional: store some info about the attempts
    reporter_phones = models.TextField(_('Reporter Phones'), blank=True, help_text=_('Comma-separated list of phone numbers that attempted'))
    
    class Meta:
        verbose_name = _('QR Scan Attempt')
        verbose_name_plural = _('QR Scan Attempts')
        unique_together = ['platform_location', 'original_complaint']
    
    def __str__(self):
        return f"Scan attempts for {self.platform_location.hash_id} - {self.attempt_count} attempts"
    
    def increment_attempt(self, reporter_phone=None):
        """Increment the attempt count and optionally track the phone number"""
        self.attempt_count += 1
        if reporter_phone and reporter_phone not in self.reporter_phones:
            if self.reporter_phones:
                self.reporter_phones += f", {reporter_phone}"
            else:
                self.reporter_phones = reporter_phone
        self.save()

class Complaint(models.Model):
    STATUS_CHOICES = [
        ('PENDING', _('Pending')),
        ('IN_PROGRESS', _('In Progress')),
        ('RESOLVED', _('Resolved')),
    ]
    
    station = models.ForeignKey(Station, on_delete=models.CASCADE, verbose_name=_('Station'))
    platform_location = models.ForeignKey(PlatformLocation, on_delete=models.CASCADE, verbose_name=_('Platform Location'), null=True, blank=True)
    description = models.TextField(_('Issue Description'), blank=True, null=True)
    reporter_name = models.CharField(_('Reporter Name'), max_length=100, blank=True, null=True)
    reporter_phone = models.CharField(_('Phone Number'), max_length=15)
    status = models.CharField(_('Status'), max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    complaint_number = models.CharField(_('Complaint Number'), max_length=20, unique=True, editable=False)
    is_verified = models.BooleanField(_('Is Verified'), default=False)
    assigned_worker = models.CharField(_('Assigned Worker'), max_length=100, blank=True, null=True)
    
    # Parent-child relationship for intensity tracking
    parent_complaint = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='daughter_complaints', verbose_name=_('Parent Complaint'))
    intensity_count = models.IntegerField(_('Intensity Count'), default=0, help_text=_('Number for daughter complaints (1, 2, 3...)'))
    
    # Closed status tracking
    is_closed = models.BooleanField(_('Is Closed'), default=False)
    closed_at = models.DateTimeField(_('Closed At'), null=True, blank=True)
    closed_status = models.CharField(_('Status When Closed'), max_length=20, choices=STATUS_CHOICES, null=True, blank=True)

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

    def get_closed_status_display(self):
        """Get display name for closed status"""
        if self.closed_status:
            for status_code, status_name in self.STATUS_CHOICES:
                if status_code == self.closed_status:
                    return status_name
        return _('Unknown')

    def __str__(self):
        platform_info = f" Platform {self.platform_location.platform_number}" if self.platform_location else ""
        parent_info = f" (Child #{self.intensity_count})" if self.parent_complaint else ""
        return f"Complaint {self.complaint_number} - {self.station.name}{platform_info}{parent_info}"

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

class SupportRequest(models.Model):
    PRIORITY_CHOICES = [
        ('low', _('Low - General inquiry')),
        ('medium', _('Medium - System issue affecting work')),
        ('high', _('High - Urgent issue affecting operations')),
        ('critical', _('Critical - System down/emergency')),
    ]
    
    CATEGORY_CHOICES = [
        ('login_access', _('Login/Access Issues')),
        ('complaint_management', _('Complaint Management')),
        ('qr_codes', _('QR Code Issues')),
        ('reports_analytics', _('Reports & Analytics')),
        ('system_performance', _('System Performance')),
        ('training_help', _('Training & Help')),
        ('other', _('Other')),
    ]
    
    STATUS_CHOICES = [
        ('open', _('Open')),
        ('in_progress', _('In Progress')),
        ('resolved', _('Resolved')),
        ('closed', _('Closed')),
    ]
    
    station = models.ForeignKey(Station, on_delete=models.CASCADE, verbose_name=_('Station'))
    manager = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_('Manager'))
    manager_name = models.CharField(_('Manager Name'), max_length=100)
    manager_email = models.EmailField(_('Manager Email'))
    manager_phone = models.CharField(_('Manager Phone'), max_length=15)
    
    issue_category = models.CharField(_('Issue Category'), max_length=50, choices=CATEGORY_CHOICES)
    priority = models.CharField(_('Priority'), max_length=20, choices=PRIORITY_CHOICES)
    issue_description = models.TextField(_('Issue Description'))
    steps_to_reproduce = models.TextField(_('Steps to Reproduce'), blank=True, null=True)
    
    status = models.CharField(_('Status'), max_length=20, choices=STATUS_CHOICES, default='open')
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    # Admin fields
    assigned_to = models.CharField(_('Assigned To'), max_length=100, blank=True, null=True)
    admin_notes = models.TextField(_('Admin Notes'), blank=True, null=True)
    resolved_at = models.DateTimeField(_('Resolved At'), blank=True, null=True)
    
    def __str__(self):
        return f"Support Request #{self.id} - {self.station.name} - {self.get_priority_display()}"
    
    class Meta:
        verbose_name = _('Support Request')
        verbose_name_plural = _('Support Requests')
        ordering = ['-created_at']
