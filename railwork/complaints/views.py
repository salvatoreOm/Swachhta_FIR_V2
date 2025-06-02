from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse
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
from .models import Station, Complaint, OTPVerification, ComplaintPhoto
from .forms import ComplaintForm, OTPVerificationForm

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
    station_code = request.GET.get('station')
    platform_number = request.GET.get('platform')
    
    if not all([station_code, platform_number]):
        messages.error(request, _('Invalid QR code. Please scan a valid QR code.'))
        return redirect('error')
    
    station = get_object_or_404(Station, station_code=station_code)
    
    if request.method == 'POST':
        form = ComplaintForm(request.POST, request.FILES)
        if form.is_valid():
            complaint = form.save(commit=False)
            complaint.station = station
            complaint.platform_number = platform_number
            complaint.save()
            
            # Save photos
            photos = []
            for i in range(1, 5):
                photo = request.FILES.get(f'photo_{i}')
                if photo:
                    complaint_photo = ComplaintPhoto.objects.create(
                        complaint=complaint,
                        photo=photo
                    )
                    photos.append(complaint_photo)
            
            if not photos:
                messages.error(request, _('At least one photo is required.'))
                complaint.delete()
                return redirect('submit_complaint')
            
            # Generate and save OTP
            otp = generate_otp()
            OTPVerification.objects.create(
                complaint=complaint,
                otp=otp
            )
            
            # Send OTP via Fast2SMS
            message = _("Your OTP for complaint verification is: {otp}. Please enter this to complete your complaint submission.").format(otp=otp)
            if send_sms_fast2sms(complaint.reporter_phone, message):
                return redirect('verify_otp', complaint_id=complaint.id)
            else:
                messages.error(request, _('Failed to send OTP. Please try again.'))
                complaint.delete()
                return redirect('submit_complaint')
    else:
        form = ComplaintForm()
    
    return render(request, 'complaints/submit_complaint.html', {
        'form': form,
        'station': station,
        'platform_number': platform_number,
    })

def verify_otp(request, complaint_id):
    complaint = get_object_or_404(Complaint, id=complaint_id)
    verification = get_object_or_404(OTPVerification, complaint=complaint)
    
    if request.method == 'POST':
        form = OTPVerificationForm(request.POST)
        if form.is_valid():
            if verification.attempts >= 3:
                messages.error(request, _('Maximum OTP verification attempts exceeded.'))
                complaint.delete()
                return redirect('error')
            
            if form.cleaned_data['otp'] == verification.otp:
                verification.is_verified = True
                verification.save()
                complaint.is_verified = True
                complaint.save()
                messages.success(request, _('Complaint verified successfully!'))
                return redirect('success')
            else:
                verification.attempts += 1
                verification.save()
                messages.error(request, _('Invalid OTP. Please try again.'))
    else:
        form = OTPVerificationForm()
    
    return render(request, 'complaints/verify_otp.html', {'form': form})

@login_required
def dashboard(request):
    complaints = Complaint.objects.filter(is_verified=True).order_by('-created_at')
    total_complaints = complaints.count()
    pending_complaints = complaints.filter(status='PENDING').count()
    resolved_complaints = complaints.filter(status='RESOLVED').count()
    
    return render(request, 'complaints/dashboard.html', {
        'complaints': complaints,
        'total_complaints': total_complaints,
        'pending_complaints': pending_complaints,
        'resolved_complaints': resolved_complaints,
    })

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
