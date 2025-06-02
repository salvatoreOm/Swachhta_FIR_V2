from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext as _
import qrcode
import random
import string
import requests
from io import BytesIO
from .models import Station, Complaint, OTPVerification, ComplaintPhoto, City, PlatformLocation, LocationType
from .forms import ComplaintForm, OTPVerificationForm
from django.core.exceptions import PermissionDenied
import json
import os
from zipfile import ZipFile
from django.core.files.base import ContentFile
from PIL import Image

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
            complaint = form.save()
            
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
        if 'station' in request.GET:
            station = get_object_or_404(Station, id=request.GET['station'])
            initial['station'] = station
            
            if 'platform' in request.GET and 'location' in request.GET:
                platform_location = get_object_or_404(
                    PlatformLocation,
                    station=station,
                    platform_number=request.GET['platform'],
                    location_type_id=request.GET['location']
                )
                initial['platform_location'] = platform_location
        
        form = ComplaintForm(initial=initial)
    
    return render(request, 'complaints/submit_complaint.html', {'form': form})

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
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            city_name = data.get('city_name')
            city_code = data.get('city_code')
            station_name = data.get('station_name')
            station_code = data.get('station_code')
            total_platforms = int(data.get('total_platforms', 1))
            platform_locations = data.get('platform_locations', [])

            # Create or get city
            city, created = City.objects.get_or_create(
                code=city_code,
                defaults={'name': city_name, 'admin': request.user}
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

            # Create station
            station = Station.objects.create(
                name=station_name,
                station_code=station_code,
                city=city,
                total_platforms=total_platforms
            )

            # Create platform locations
            created_locations = []
            for platform_data in platform_locations:
                platform_number = platform_data['platform_number']
                location_types = platform_data['location_types']
                
                for location_type_id in location_types:
                    location_type = LocationType.objects.get(id=location_type_id)
                    platform_location = PlatformLocation.objects.create(
                        station=station,
                        platform_number=platform_number,
                        location_type=location_type
                    )
                    created_locations.append({
                        'id': platform_location.id,
                        'platform_number': platform_number,
                        'location_type_name': location_type.name,
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
    
    # GET request - show setup form
    location_types = LocationType.objects.all()
    context = {
        'location_types': location_types
    }
    return render(request, 'complaints/station_setup.html', context)

@login_required
def download_qr_codes(request, station_id):
    station = get_object_or_404(Station, id=station_id)
    
    # Check permissions
    if not request.user.is_superuser and station.city.admin != request.user:
        raise PermissionDenied(_("You don't have permission to download QR codes for this station."))
    
    # Create a ZIP file
    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, 'w') as zip_file:
        for platform_location in station.platform_locations.all():
            if platform_location.qr_code:
                qr_name = f"platform_{platform_location.platform_number}_{platform_location.location_type.name}.png"
                zip_file.writestr(qr_name, platform_location.qr_code.read())
    
    # Return the ZIP file
    response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename={station.station_code}_qr_codes.zip'
    return response

@login_required
@require_http_methods(['POST'])
def update_complaint_status(request, complaint_id):
    complaint = get_object_or_404(Complaint, id=complaint_id)
    new_status = request.POST.get('status')
    
    if new_status in dict(Complaint.STATUS_CHOICES):
        complaint.status = new_status
        complaint.save()
        messages.success(request, _('Complaint status updated to {status}').format(status=new_status))
    else:
        messages.error(request, _('Invalid status'))
    
    return redirect('dashboard')

@login_required
@require_http_methods(['POST'])
def assign_worker(request, complaint_id):
    complaint = get_object_or_404(Complaint, id=complaint_id)
    
    # Check if user has permission to modify this complaint
    if not request.user.is_superuser and complaint.station.city.admin != request.user:
        raise PermissionDenied(_("You don't have permission to assign workers to this complaint."))
    
    worker_name = request.POST.get('worker_name')
    complaint.assigned_worker = worker_name
    complaint.save()
    
    return JsonResponse({
        'status': 'success',
        'message': _('Worker assigned successfully')
    })
