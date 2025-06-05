from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.views import PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView
from django.utils.translation import gettext as _
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone
from datetime import datetime, timedelta
import qrcode
import random
import string
import requests
from io import BytesIO
from .models import Station, Complaint, OTPVerification, ComplaintPhoto, City, PlatformLocation, LocationType, UserProfile, QRScanAttempt, SupportRequest
from .forms import ComplaintForm, OTPVerificationForm
from django.core.exceptions import PermissionDenied
import json
import os
from zipfile import ZipFile
from django.core.files.base import ContentFile
from PIL import Image
from django.db import models

# Authentication Views
def user_login(request):
    """Custom login view for station managers"""
    if request.user.is_authenticated:
        return redirect('user_dashboard')
    
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        try:
            user = User.objects.get(email=email)
            user = authenticate(request, username=user.username, password=password)
            if user is not None:
                login(request, user)
                next_url = request.GET.get('next', 'user_dashboard')
                return redirect(next_url)
            else:
                messages.error(request, _('Invalid email or password.'))
        except User.DoesNotExist:
            messages.error(request, _('Invalid email or password.'))
    
    return render(request, 'complaints/auth/login.html')

@login_required
def user_logout(request):
    """Custom logout view"""
    logout(request)
    messages.success(request, _('You have been successfully logged out.'))
    return redirect('user_login')

def user_password_reset(request):
    """Custom password reset view"""
    if request.method == 'POST':
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            form.save(
                request=request,
                use_https=request.is_secure(),
                email_template_name='complaints/auth/password_reset_email.txt',
                subject_template_name='complaints/auth/password_reset_subject.txt',
            )
            messages.success(request, _('Password reset email has been sent to your email address.'))
            return redirect('password_reset_done')
    else:
        form = PasswordResetForm()
    
    return render(request, 'complaints/auth/password_reset.html', {'form': form})

def password_reset_done(request):
    """Password reset done view"""
    return render(request, 'complaints/auth/password_reset_done.html')

@login_required
def user_dashboard(request):
    """Custom dashboard for station managers with restricted access"""
    # Prevent access to superusers and staff - redirect them to admin
    if request.user.is_superuser or request.user.is_staff:
        return redirect('/admin/')
    
    # Get user's station
    try:
        user_profile = UserProfile.objects.get(user=request.user)
        user_station = user_profile.station
    except UserProfile.DoesNotExist:
        try:
            user_station = request.user.managed_station
        except Station.DoesNotExist:
            user_station = None
    
    if not user_station:
        messages.error(request, _('No station assigned to your account. Please contact administrator.'))
        return render(request, 'complaints/auth/no_station.html')
    
    # Get tab parameter
    tab = request.GET.get('tab', 'recent')
    
    # Get all complaints for user's station
    all_complaints = Complaint.objects.filter(station=user_station)
    
    if tab == 'closed':
        # Show closed complaints
        complaints = all_complaints.filter(is_closed=True).order_by('-closed_at')
        # Statistics for closed complaints
        total_complaints = complaints.count()
        pending_complaints = complaints.filter(closed_status='PENDING').count()
        in_progress_complaints = complaints.filter(closed_status='IN_PROGRESS').count()
        resolved_complaints = complaints.filter(closed_status='RESOLVED').count()
    else:
        # Show recent (non-closed) complaints
        complaints = all_complaints.filter(is_closed=False).order_by('-created_at')
        # Statistics for recent complaints
        total_complaints = complaints.count()
        pending_complaints = complaints.filter(status='PENDING').count()
        in_progress_complaints = complaints.filter(status='IN_PROGRESS').count()
        resolved_complaints = complaints.filter(status='RESOLVED').count()
    
    context = {
        'complaints': complaints,
        'user_station': user_station,
        'total_complaints': total_complaints,
        'pending_complaints': pending_complaints,
        'in_progress_complaints': in_progress_complaints,
        'resolved_complaints': resolved_complaints,
        'active_tab': tab,
    }
    return render(request, 'complaints/user_dashboard.html', context)

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

def send_sms_fast2sms(phone_number, message):
    url = "https://www.fast2sms.com/dev/bulkV2"
    headers = {
        'authorization': settings.FAST2SMS_API_KEY,
        'Content-Type': "application/x-www-form-urlencoded"
    }
    payload = {
        "route": "v3",
        "sender_id": "TXTIND",
        "message": message,
        "language": "unicode",
        "numbers": phone_number,
    }
    
    try:
        response = requests.post(url, headers=headers, data=payload)
        return response.json()['return']
    except Exception as e:
        print(f"SMS sending failed: {str(e)}")
        return False

def generate_station_qr(request, station_code, platform_number):
    station = get_object_or_404(Station, station_code=station_code)
    
    # Generate the complaint URL with station and platform info
    complaint_url = request.build_absolute_uri(
        reverse('submit_complaint') + 
        f'?station={station_code}&platform={platform_number}'
    )
    
    # Create QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(complaint_url)
    qr.make(fit=True)
    
    # Create image
    img_buffer = BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(img_buffer)
    img_buffer.seek(0)
    
    return HttpResponse(img_buffer.getvalue(), content_type="image/png")

def submit_complaint(request):
    if request.method == 'POST':
        form = ComplaintForm(request.POST, request.FILES)
        if form.is_valid():
            complaint = form.save(commit=False)
            
            # Smart QR Logic: Check if there's already a complaint for this location within 15 minutes
            if complaint.platform_location:
                fifteen_minutes_ago = timezone.now() - timedelta(minutes=15)
                
                # Check for ANY complaint (not just IN_PROGRESS) from the same location within 15 minutes
                existing_recent_complaint = Complaint.objects.filter(
                    platform_location=complaint.platform_location,
                    created_at__gte=fifteen_minutes_ago,
                    is_closed=False,
                    is_verified=True  # Only consider verified complaints
                ).first()
                
                if existing_recent_complaint:
                    # Track this duplicate attempt
                    scan_attempt, created = QRScanAttempt.objects.get_or_create(
                        platform_location=complaint.platform_location,
                        original_complaint=existing_recent_complaint,
                        defaults={'attempt_count': 1, 'reporter_phones': complaint.reporter_phone}
                    )
                    
                    if not created:
                        # Increment existing attempt count
                        scan_attempt.increment_attempt(complaint.reporter_phone)
                    
                    # Don't create a new complaint - redirect to "already in progress" page
                    return redirect('complaint_already_in_progress', 
                                  hash_id=complaint.platform_location.hash_id,
                                  existing_complaint_id=existing_recent_complaint.id)
                
                # If no recent complaint, proceed with parent-child logic for intensity tracking
                parent_complaint = Complaint.objects.filter(
                    platform_location=complaint.platform_location,
                    status='IN_PROGRESS',
                    created_at__gte=fifteen_minutes_ago,
                    parent_complaint__isnull=True,  # Only look for parent complaints
                    is_closed=False
                ).first()
                
                if parent_complaint:
                    # This becomes a daughter complaint
                    complaint.parent_complaint = parent_complaint
                    complaint.status = 'IN_PROGRESS'
                    complaint.assigned_worker = parent_complaint.assigned_worker
                    
                    # Calculate intensity count
                    existing_daughters = parent_complaint.daughter_complaints.count()
                    complaint.intensity_count = existing_daughters + 1
            
            complaint.save()
            
            # Handle multiple photo uploads
            photos = []
            for i in range(1, 5):  # photo_1 to photo_4
                photo = request.FILES.get(f'photo_{i}')
                if photo:
                    ComplaintPhoto.objects.create(complaint=complaint, photo=photo)
                    photos.append(photo)
            
            # Generate and save OTP
            otp = ''.join(random.choices(string.digits, k=6))
            OTPVerification.objects.create(complaint=complaint, otp=otp)
            
            # Send OTP via SMS
            if settings.FAST2SMS_API_KEY:
                url = "https://www.fast2sms.com/dev/bulkV2"
                payload = {
                    "message": f"Your OTP for complaint verification is: {otp}",
                    "language": "english",
                    "route": "q",
                    "numbers": complaint.reporter_phone,
                }
                headers = {
                    "authorization": settings.FAST2SMS_API_KEY,
                }
                response = requests.post(url, data=payload, headers=headers)
            
            return redirect('verify_otp', complaint_id=complaint.id)
    else:
        initial = {}
        station = None
        platform_location = None
        
        # Handle QR scan parameters
        if 'station' in request.GET:
            try:
                station = get_object_or_404(Station, id=request.GET['station'])
                initial['station'] = station
                
                # Handle location parameter (refers to platform_location ID)
                if 'location' in request.GET:
                    try:
                        platform_location = get_object_or_404(PlatformLocation, id=request.GET['location'])
                        initial['platform_location'] = platform_location
                    except:
                        # Fallback for old QR codes that might still use platform+location_type format
                        if 'platform' in request.GET:
                            try:
                                platform_location = PlatformLocation.objects.filter(
                                    station=station,
                                    platform_number=request.GET['platform'],
                                    location_type_id=request.GET['location']
                                ).first()
                                if platform_location:
                                    initial['platform_location'] = platform_location
                            except:
                                pass
            except:
                pass
        
        form = ComplaintForm(initial=initial)
        
        # Prepare context with location details for template display
        context = {
            'form': form,
            'station': station,
            'platform_location': platform_location,
            'platform_number': platform_location.platform_number if platform_location else None,
            'location_description': platform_location.location_description if platform_location else None,
        }
    
    return render(request, 'complaints/submit_complaint.html', context)

def verify_otp(request, complaint_id):
    complaint = get_object_or_404(Complaint, id=complaint_id)
    otp_verification = get_object_or_404(OTPVerification, complaint=complaint)
    
    if request.method == 'POST':
        form = OTPVerificationForm(request.POST, instance=otp_verification)
        if form.is_valid():
            if form.cleaned_data['otp'] == otp_verification.otp:
                otp_verification.is_verified = True
                otp_verification.save()
                complaint.is_verified = True
                complaint.save()
                messages.success(request, _('Complaint verified successfully!'))
                return redirect('complaint_success', complaint_id=complaint.id)
            else:
                otp_verification.attempts += 1
                otp_verification.save()
                messages.error(request, _('Invalid OTP. Please try again.'))
    else:
        form = OTPVerificationForm(instance=otp_verification)
    
    return render(request, 'complaints/verify_otp.html', {'form': form, 'complaint': complaint})

def complaint_success(request, complaint_id):
    complaint = get_object_or_404(Complaint, id=complaint_id)
    return render(request, 'complaints/success.html', {'complaint': complaint})

def complaint_already_in_progress(request, hash_id, existing_complaint_id):
    """Show page when user tries to submit complaint for location that already has recent complaint"""
    try:
        existing_complaint = get_object_or_404(Complaint, id=existing_complaint_id)
        platform_location = existing_complaint.platform_location
        
        # Calculate time since existing complaint
        time_since = existing_complaint.created_at
        minutes_ago = int((timezone.now() - time_since).total_seconds() / 60)
        
        # Get the scan attempt count for this location and complaint
        try:
            scan_attempt = QRScanAttempt.objects.get(
                platform_location=platform_location,
                original_complaint=existing_complaint
            )
            attempt_count = scan_attempt.attempt_count
            total_attempts = attempt_count + 1  # +1 for the original complaint
        except QRScanAttempt.DoesNotExist:
            attempt_count = 0
            total_attempts = 1
        
        context = {
            'hash_id': hash_id,
            'platform_location': platform_location,
            'existing_complaint': existing_complaint,
            'minutes_ago': minutes_ago,
            'station': platform_location.station if platform_location else None,
            'attempt_count': attempt_count,
            'total_attempts': total_attempts,
        }
        return render(request, 'complaints/already_in_progress.html', context)
    except:
        # If there's any error, redirect to regular complaint form
        return redirect('submit_complaint')

@login_required
def dashboard(request):
    # For superuser, show all complaints
    # For city admin, show only their city's complaints
    if request.user.is_superuser:
        complaints = Complaint.objects.all().order_by('-created_at')
        stations = Station.objects.all()
        cities = City.objects.all()
    else:
        cities = City.objects.filter(admin=request.user)
        stations = Station.objects.filter(city__admin=request.user)
        complaints = Complaint.objects.filter(station__city__admin=request.user).order_by('-created_at')
    
    context = {
        'complaints': complaints,
        'stations': stations,
        'cities': cities,
    }
    return render(request, 'complaints/dashboard.html', context)

@login_required
def station_setup(request):
    # Prevent regular users from creating stations if they already have one
    if not request.user.is_superuser and not request.user.is_staff:
        try:
            existing_station = request.user.managed_station
            messages.error(request, _('You already have a station assigned. You cannot create another station.'))
            return redirect('user_dashboard')
        except Station.DoesNotExist:
            pass  # User doesn't have a station yet, can create one
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            city_name = data.get('city_name')
            city_code = data.get('city_code')
            station_name = data.get('station_name')
            station_code = data.get('station_code')
            total_platforms = int(data.get('total_platforms', 1))
            platform_locations = data.get('platform_locations', [])

            # For regular users, limit to one station
            if not request.user.is_superuser and not request.user.is_staff:
                try:
                    existing_station = request.user.managed_station
                    return JsonResponse({
                        'status': 'error',
                        'message': _('You already have a station assigned. You cannot create another station.')
                    }, status=403)
                except Station.DoesNotExist:
                    pass

            # Create or get city
            city, created = City.objects.get_or_create(
                code=city_code,
                defaults={'name': city_name, 'admin': request.user if request.user.is_superuser else None}
            )

            if not created and city.admin != request.user and not request.user.is_superuser:
                raise PermissionDenied(_("You don't have permission to add stations to this city."))

            # Check if station already exists
            existing_station = Station.objects.filter(
                station_code=station_code,
                city=city
            ).first()

            if existing_station:
                return JsonResponse({
                    'status': 'error',
                    'message': _('A station with this code already exists in this city. Please use a different station code.')
                }, status=400)

            # Create station and assign manager
            station = Station.objects.create(
                name=station_name,
                station_code=station_code,
                city=city,
                total_platforms=total_platforms,
                manager=request.user if not request.user.is_superuser else None
            )

            # Create or update user profile
            if not request.user.is_superuser and not request.user.is_staff:
                user_profile, created = UserProfile.objects.get_or_create(user=request.user)
                user_profile.station = station
                user_profile.save()

            # Create platform locations with custom descriptions
            created_locations = []
            for platform_data in platform_locations:
                platform_number = platform_data['platform_number']
                locations = platform_data['locations']  # List of custom location descriptions
                
                for location_description in locations:
                    platform_location = PlatformLocation.objects.create(
                        station=station,
                        platform_number=platform_number,
                        location_description=location_description
                    )
                    created_locations.append({
                        'id': platform_location.id,
                        'platform_number': platform_number,
                        'location_description': location_description,
                        'hash_id': platform_location.hash_id,
                        'qr_code_url': platform_location.qr_code.url if platform_location.qr_code else None
                    })

            return JsonResponse({
                'status': 'success',
                'message': _('Station setup completed successfully'),
                'station_id': station.id,
                'locations': created_locations
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
    
    # GET request - show setup form (no need for location_types anymore)
    context = {}
    return render(request, 'complaints/station_setup.html', context)

@login_required
def download_qr_codes(request, station_id):
    station = get_object_or_404(Station, id=station_id)
    
    # Check permissions - superuser/staff can access all, regular users only their station
    if not request.user.is_superuser and not request.user.is_staff:
        try:
            user_station = request.user.managed_station
            if user_station != station:
                raise PermissionDenied(_("You don't have permission to download QR codes for this station."))
        except Station.DoesNotExist:
            raise PermissionDenied(_("You don't have a station assigned."))
    elif not request.user.is_superuser and station.city.admin != request.user:
        raise PermissionDenied(_("You don't have permission to download QR codes for this station."))
    
    # Create a ZIP file
    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, 'w') as zip_file:
        for platform_location in station.platform_locations.all():
            if platform_location.qr_code:
                # Use hash_id and location_description for better organization
                location_name = platform_location.location_description.replace(' ', '_').replace(',', '').replace('/', '_')
                qr_name = f"{platform_location.hash_id}_{location_name}.png"
                zip_file.writestr(qr_name, platform_location.qr_code.read())
    
    # Return the ZIP file
    response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename={station.station_code}_qr_codes.zip'
    return response

@login_required
@require_http_methods(['POST'])
def update_complaint_status(request, complaint_id):
    complaint = get_object_or_404(Complaint, id=complaint_id)
    
    # Check permissions - users can only update complaints for their station
    if not request.user.is_superuser and not request.user.is_staff:
        try:
            user_station = request.user.managed_station
            if complaint.station != user_station:
                raise PermissionDenied(_("You don't have permission to update this complaint."))
        except Station.DoesNotExist:
            raise PermissionDenied(_("You don't have a station assigned."))
    elif not request.user.is_superuser and complaint.station.city.admin != request.user:
        raise PermissionDenied(_("You don't have permission to update this complaint."))
    
    # Prevent changes to closed complaints
    if complaint.is_closed:
        messages.error(request, _('Cannot update status of a closed complaint.'))
        if request.user.is_superuser or request.user.is_staff:
            return redirect('dashboard')
        else:
            return redirect('user_dashboard')
    
    new_status = request.POST.get('status')
    
    if new_status in dict(Complaint.STATUS_CHOICES):
        old_status = complaint.status
        complaint.status = new_status
        complaint.save()
        
        # If this is a parent complaint and status changes, update all daughter complaints
        if complaint.parent_complaint is None and complaint.daughter_complaints.exists():
            if new_status != 'IN_PROGRESS':
                # Auto-resolve all daughter complaints when parent status changes away from IN_PROGRESS
                complaint.daughter_complaints.filter(is_closed=False).update(
                    status='RESOLVED',
                    updated_at=timezone.now()
                )
                messages.info(request, _('All related intensity complaints have been auto-resolved.'))
        
        messages.success(request, _('Complaint status updated to {status}').format(status=new_status))
    else:
        messages.error(request, _('Invalid status'))
    
    # Redirect based on user type
    if request.user.is_superuser or request.user.is_staff:
        return redirect('dashboard')
    else:
        return redirect('user_dashboard')

@login_required
@require_http_methods(['POST'])
def close_complaint(request, complaint_id):
    complaint = get_object_or_404(Complaint, id=complaint_id)
    
    # Check permissions - users can only close complaints for their station
    if not request.user.is_superuser and not request.user.is_staff:
        try:
            user_station = request.user.managed_station
            if complaint.station != user_station:
                raise PermissionDenied(_("You don't have permission to close this complaint."))
        except Station.DoesNotExist:
            raise PermissionDenied(_("You don't have a station assigned."))
    elif not request.user.is_superuser and complaint.station.city.admin != request.user:
        raise PermissionDenied(_("You don't have permission to close this complaint."))
    
    # Prevent double-closing
    if complaint.is_closed:
        messages.error(request, _('Complaint is already closed.'))
    else:
        # Close the complaint
        complaint.is_closed = True
        complaint.closed_at = timezone.now()
        complaint.closed_status = complaint.status
        complaint.save()
        
        # If this is a parent complaint, close all daughter complaints too
        if complaint.parent_complaint is None and complaint.daughter_complaints.exists():
            complaint.daughter_complaints.filter(is_closed=False).update(
                is_closed=True,
                closed_at=timezone.now(),
                closed_status=models.F('status')
            )
            messages.info(request, _('All related intensity complaints have been closed as well.'))
        
        messages.success(request, _('Complaint has been closed successfully.'))
    
    # Redirect based on user type
    if request.user.is_superuser or request.user.is_staff:
        return redirect('dashboard')
    else:
        return redirect('user_dashboard')

@login_required
@require_http_methods(['POST'])
def assign_worker(request, complaint_id):
    complaint = get_object_or_404(Complaint, id=complaint_id)
    
    # Check permissions - users can only assign workers to complaints for their station
    if not request.user.is_superuser and not request.user.is_staff:
        try:
            user_station = request.user.managed_station
            if complaint.station != user_station:
                raise PermissionDenied(_("You don't have permission to assign workers to this complaint."))
        except Station.DoesNotExist:
            raise PermissionDenied(_("You don't have a station assigned."))
    elif not request.user.is_superuser and complaint.station.city.admin != request.user:
        raise PermissionDenied(_("You don't have permission to assign workers to this complaint."))
    
    # Prevent changes to closed complaints
    if complaint.is_closed:
        messages.error(request, _('Cannot assign worker to a closed complaint.'))
        if request.user.is_superuser or request.user.is_staff:
            return redirect('dashboard')
        else:
            return redirect('user_dashboard')
    
    worker_name = request.POST.get('worker_name')
    
    if worker_name:
        complaint.assigned_worker = worker_name
        complaint.save()
        messages.success(request, _('Worker assigned successfully'))
    else:
        messages.error(request, _('Please provide worker name'))
    
    # Redirect based on user type
    if request.user.is_superuser or request.user.is_staff:
        return redirect('dashboard')
    else:
        return redirect('user_dashboard')

@login_required
def view_complaint_photo(request, photo_id):
    """View a specific complaint photo"""
    photo = get_object_or_404(ComplaintPhoto, id=photo_id)
    complaint = photo.complaint
    
    # Check permissions - users can only view photos for complaints in their station/city
    if not request.user.is_superuser and not request.user.is_staff:
        try:
            user_station = request.user.managed_station
            if complaint.station != user_station:
                raise PermissionDenied(_("You don't have permission to view this photo."))
        except Station.DoesNotExist:
            raise PermissionDenied(_("You don't have a station assigned."))
    elif not request.user.is_superuser and complaint.station.city.admin != request.user:
        raise PermissionDenied(_("You don't have permission to view this photo."))
    
    return render(request, 'complaints/view_photo.html', {
        'photo': photo,
        'complaint': complaint
    })

@login_required
def station_analytics(request):
    """Analytics dashboard for station managers showing detailed statistics"""
    # Only allow regular users to view analytics for their station
    if request.user.is_superuser or request.user.is_staff:
        messages.error(request, _('Superusers and staff should use the admin panel for analytics.'))
        return redirect('dashboard')
    
    # Get user's station
    try:
        user_profile = UserProfile.objects.get(user=request.user)
        station = user_profile.station
    except UserProfile.DoesNotExist:
        try:
            station = request.user.managed_station
        except Station.DoesNotExist:
            station = None
    
    if not station:
        messages.error(request, _('No station assigned to your account.'))
        return redirect('user_dashboard')
    
    # Get all complaints for this station
    complaints = Complaint.objects.filter(station=station)
    
    # Overall statistics
    total_complaints = complaints.count()
    pending_complaints = complaints.filter(status='PENDING').count()
    in_progress_complaints = complaints.filter(status='IN_PROGRESS').count()
    resolved_complaints = complaints.filter(status='RESOLVED').count()
    closed_complaints = complaints.filter(is_closed=True).count()
    
    # Daily Analytics - Today's statistics
    today = timezone.now().date()
    today_complaints = complaints.filter(created_at__date=today)
    today_stats = {
        'total': today_complaints.count(),
        'pending': today_complaints.filter(status='PENDING').count(),
        'in_progress': today_complaints.filter(status='IN_PROGRESS').count(),
        'resolved': today_complaints.filter(status='RESOLVED').count(),
        'closed': today_complaints.filter(is_closed=True).count(),
    }
    
    # Yesterday's statistics for comparison
    yesterday = today - timedelta(days=1)
    yesterday_complaints = complaints.filter(created_at__date=yesterday)
    yesterday_stats = {
        'total': yesterday_complaints.count(),
        'pending': yesterday_complaints.filter(status='PENDING').count(),
        'in_progress': yesterday_complaints.filter(status='IN_PROGRESS').count(),
        'resolved': yesterday_complaints.filter(status='RESOLVED').count(),
        'closed': yesterday_complaints.filter(is_closed=True).count(),
    }
    
    # Daily trend (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    daily_data = []
    for i in range(30):
        date = (timezone.now() - timedelta(days=i)).date()
        day_complaints = complaints.filter(created_at__date=date)
        daily_data.append({
            'date': date.strftime('%Y-%m-%d'),
            'date_display': date.strftime('%b %d'),
            'total': day_complaints.count(),
            'pending': day_complaints.filter(status='PENDING').count(),
            'in_progress': day_complaints.filter(status='IN_PROGRESS').count(),
            'resolved': day_complaints.filter(status='RESOLVED').count(),
            'closed': day_complaints.filter(is_closed=True).count(),
        })
    daily_data.reverse()  # Show oldest to newest
    
    # Hourly pattern analysis (today)
    hourly_stats = []
    for hour in range(24):
        hour_start = timezone.now().replace(hour=hour, minute=0, second=0, microsecond=0)
        hour_end = hour_start + timedelta(hours=1)
        hour_complaints = today_complaints.filter(
            created_at__gte=hour_start,
            created_at__lt=hour_end
        )
        hourly_stats.append({
            'hour': hour,
            'hour_display': f"{hour:02d}:00",
            'count': hour_complaints.count(),
        })
    
    # Weekly pattern (last 7 days)
    weekly_stats = []
    for i in range(7):
        date = (timezone.now() - timedelta(days=i)).date()
        day_complaints = complaints.filter(created_at__date=date)
        weekly_stats.append({
            'date': date,
            'day_name': date.strftime('%A'),
            'day_short': date.strftime('%a'),
            'count': day_complaints.count(),
        })
    weekly_stats.reverse()
    
    # Top complaint locations (daily)
    today_location_stats = []
    for location in station.platform_locations.all():
        location_today = today_complaints.filter(platform_location=location)
        
        # Get scan attempt data for this location
        scan_attempts_today = QRScanAttempt.objects.filter(
            platform_location=location,
            last_attempt_at__date=today
        )
        total_scan_attempts = sum(attempt.attempt_count for attempt in scan_attempts_today)
        
        if location_today.count() > 0 or total_scan_attempts > 0:
            today_location_stats.append({
                'location': location,
                'count': location_today.count(),
                'pending': location_today.filter(status='PENDING').count(),
                'resolved': location_today.filter(status='RESOLVED').count(),
                'scan_attempts': total_scan_attempts,
                'total_interest': location_today.count() + total_scan_attempts,  # Combined metric
            })
    today_location_stats.sort(key=lambda x: x['total_interest'], reverse=True)
    
    # Platform-wise statistics
    platform_stats = []
    for platform_num in range(1, station.total_platforms + 1):
        platform_complaints = complaints.filter(platform_location__platform_number=platform_num)
        platform_today = today_complaints.filter(platform_location__platform_number=platform_num)
        platform_stats.append({
            'platform_number': platform_num,
            'total': platform_complaints.count(),
            'today': platform_today.count(),
            'pending': platform_complaints.filter(status='PENDING').count(),
            'in_progress': platform_complaints.filter(status='IN_PROGRESS').count(),
            'resolved': platform_complaints.filter(status='RESOLVED').count(),
            'closed': platform_complaints.filter(is_closed=True).count(),
        })
    
    # QR Location-wise statistics
    qr_location_stats = []
    for location in station.platform_locations.all():
        location_complaints = complaints.filter(platform_location=location)
        qr_location_stats.append({
            'location': location,
            'total': location_complaints.count(),
            'pending': location_complaints.filter(status='PENDING').count(),
            'resolved': location_complaints.filter(status='RESOLVED').count(),
        })
    
    # Worker performance statistics
    worker_stats = complaints.exclude(assigned_worker__isnull=True).exclude(assigned_worker='').values('assigned_worker').annotate(
        total_assigned=Count('id'),
        resolved_count=Count('id', filter=Q(status='RESOLVED')),
        closed_count=Count('id', filter=Q(is_closed=True))
    ).order_by('-resolved_count')
    
    # Monthly trend (last 12 months)
    end_date = timezone.now()
    start_date = end_date - timedelta(days=365)
    
    monthly_data = complaints.filter(
        created_at__range=[start_date, end_date]
    ).annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        count=Count('id')
    ).order_by('month')
    
    # Status distribution for charts
    status_distribution = {
        'pending': pending_complaints,
        'in_progress': in_progress_complaints,
        'resolved': resolved_complaints,
        'closed': closed_complaints,
    }
    
    # Recent activity (last 30 days)
    recent_complaints = complaints.filter(created_at__gte=thirty_days_ago).order_by('-created_at')[:10]
    
    # Calculate percentage changes from yesterday
    def calculate_change(today_val, yesterday_val):
        if yesterday_val == 0:
            return 100 if today_val > 0 else 0
        return round(((today_val - yesterday_val) / yesterday_val) * 100, 1)
    
    daily_changes = {
        'total': calculate_change(today_stats['total'], yesterday_stats['total']),
        'pending': calculate_change(today_stats['pending'], yesterday_stats['pending']),
        'in_progress': calculate_change(today_stats['in_progress'], yesterday_stats['in_progress']),
        'resolved': calculate_change(today_stats['resolved'], yesterday_stats['resolved']),
    }
    
    context = {
        'station': station,
        'total_complaints': total_complaints,
        'pending_complaints': pending_complaints,
        'in_progress_complaints': in_progress_complaints,
        'resolved_complaints': resolved_complaints,
        'closed_complaints': closed_complaints,
        
        # Daily analytics
        'today_stats': today_stats,
        'yesterday_stats': yesterday_stats,
        'daily_changes': daily_changes,
        'daily_data': daily_data,
        'hourly_stats': hourly_stats,
        'weekly_stats': weekly_stats,
        'today_location_stats': today_location_stats,
        
        # Existing analytics
        'platform_stats': platform_stats,
        'qr_location_stats': qr_location_stats,
        'worker_stats': worker_stats,
        'monthly_data': monthly_data,
        'status_distribution': status_distribution,
        'recent_complaints': recent_complaints,
    }
    
    return render(request, 'complaints/station_analytics.html', context)

@login_required
def manage_station(request):
    """Allow station managers to edit their station details and manage QR codes"""
    # Only allow regular users to manage their station
    if request.user.is_superuser or request.user.is_staff:
        messages.error(request, _('Superusers and staff should use the admin panel for station management.'))
        return redirect('dashboard')
    
    # Get user's station
    try:
        user_profile = UserProfile.objects.get(user=request.user)
        station = user_profile.station
    except UserProfile.DoesNotExist:
        try:
            station = request.user.managed_station
        except Station.DoesNotExist:
            station = None
    
    if not station:
        messages.error(request, _('No station assigned to your account.'))
        return redirect('user_dashboard')
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            # Station name is now unchangeable - remove station_name from updates
            total_platforms = int(data.get('total_platforms', station.total_platforms))
            new_locations = data.get('new_locations', [])
            updated_locations = data.get('updated_locations', [])
            deleted_locations = data.get('deleted_locations', [])
            
            # Update station details (only total_platforms, not name)
            station.total_platforms = total_platforms
            station.save()
            
            # Update existing locations
            for update in updated_locations:
                try:
                    location = PlatformLocation.objects.get(id=update['id'], station=station)
                    location.location_description = update['location_description']
                    location.save()
                except PlatformLocation.DoesNotExist:
                    continue
            
            # Delete locations (only if they have no complaints)
            deleted_count = 0
            for location_id in deleted_locations:
                try:
                    location = PlatformLocation.objects.get(id=location_id, station=station)
                    # Check if location has complaints
                    if not location.complaint_set.exists():
                        location.delete()
                        deleted_count += 1
                except PlatformLocation.DoesNotExist:
                    continue
            
            # Create new locations
            created_count = 0
            for platform_data in new_locations:
                platform_number = platform_data['platform_number']
                locations = platform_data['locations']
                
                for location_description in locations:
                    PlatformLocation.objects.create(
                        station=station,
                        platform_number=platform_number,
                        location_description=location_description
                    )
                    created_count += 1
            
            message_parts = []
            if created_count > 0:
                message_parts.append(f'{created_count} new QR codes created')
            if deleted_count > 0:
                message_parts.append(f'{deleted_count} QR codes deleted')
            if not message_parts:
                message_parts.append('Station updated successfully')
            
            return JsonResponse({
                'status': 'success',
                'message': _('. '.join(message_parts) + '.')
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
    
    # GET request - show manage form
    # Get existing platform locations
    platform_locations = station.platform_locations.all().order_by('platform_number', 'id')
    
    # Prepare location data for JavaScript
    existing_locations = []
    for location in platform_locations:
        has_complaints = location.complaint_set.exists()
        existing_locations.append({
            'id': location.id,
            'platform_number': location.platform_number,
            'location_description': location.location_description,
            'hash_id': location.hash_id,
            'qr_code_url': location.qr_code.url if location.qr_code else None,
            'has_complaints': has_complaints
        })
    
    context = {
        'station': station,
        'existing_locations': json.dumps(existing_locations)
    }
    return render(request, 'complaints/manage_station.html', context)

@login_required
def support_request(request):
    """Technical support form for station managers"""
    # Only allow regular users (station managers)
    if request.user.is_superuser or request.user.is_staff:
        messages.error(request, _('Support requests are for station managers only.'))
        return redirect('dashboard')
    
    # Get user's station
    try:
        user_profile = UserProfile.objects.get(user=request.user)
        user_station = user_profile.station
    except UserProfile.DoesNotExist:
        try:
            user_station = request.user.managed_station
        except Station.DoesNotExist:
            user_station = None
    
    if not user_station:
        messages.error(request, _('No station assigned to your account.'))
        return redirect('user_dashboard')
    
    if request.method == 'POST':
        try:
            # Create support request
            support_request = SupportRequest.objects.create(
                station=user_station,
                manager=request.user,
                manager_name=request.POST.get('manager_name'),
                manager_email=request.POST.get('manager_email'),
                manager_phone=request.POST.get('manager_phone'),
                issue_category=request.POST.get('issue_category'),
                priority=request.POST.get('priority'),
                issue_description=request.POST.get('issue_description'),
                steps_to_reproduce=request.POST.get('steps_to_reproduce', '')
            )
            
            # Send email notification to technical team
            if settings.EMAIL_HOST:
                subject = f'[{support_request.get_priority_display()}] Support Request #{support_request.id} - {user_station.name}'
                
                message = f"""
                New support request received:
                
                Station: {user_station.name} ({user_station.station_code})
                Manager: {support_request.manager_name}
                Email: {support_request.manager_email}
                Phone: {support_request.manager_phone}
                
                Category: {support_request.get_issue_category_display()}
                Priority: {support_request.get_priority_display()}
                
                Description:
                {support_request.issue_description}
                
                Steps to Reproduce:
                {support_request.steps_to_reproduce}
                
                Created at: {support_request.created_at}
                """
                
                try:
                    from django.core.mail import send_mail
                    send_mail(
                        subject,
                        message,
                        settings.DEFAULT_FROM_EMAIL,
                        ['omparihar@zhecker.com'],  # Replace with your actual technical team email
                        fail_silently=True,
                    )
                except Exception as e:
                    print(f"Failed to send support email: {str(e)}")
            
            messages.success(request, _(f'Support request #{support_request.id} submitted successfully. Our technical team will contact you soon.'))
            return redirect('user_dashboard')
            
        except Exception as e:
            messages.error(request, _('Error submitting support request. Please try again.'))
            print(f"Support request error: {str(e)}")
    
    context = {
        'user_station': user_station,
    }
    return render(request, 'complaints/support_form.html', context)
