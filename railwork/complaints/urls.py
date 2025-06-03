from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from django.shortcuts import render

urlpatterns = [
    # Authentication URLs
    path('login/', views.user_login, name='user_login'),
    path('logout/', views.user_logout, name='user_logout'),
    path('password-reset/', views.user_password_reset, name='password_reset'),
    path('password-reset/done/', views.password_reset_done, name='password_reset_done'),
    path('password-reset/confirm/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(
             template_name='complaints/auth/password_reset_confirm.html',
             success_url='/password-reset/complete/'
         ), name='password_reset_confirm'),
    path('password-reset/complete/', 
         auth_views.PasswordResetCompleteView.as_view(
             template_name='complaints/auth/password_reset_complete.html'
         ), name='password_reset_complete'),
    
    # User Dashboard (non-admin)
    path('dashboard/', views.user_dashboard, name='user_dashboard'),
    
    # Admin Dashboard (for superuser/staff)
    path('admin-dashboard/', views.dashboard, name='dashboard'),
    
    # Public complaint submission
    path('submit/', views.submit_complaint, name='submit_complaint'),
    path('verify-otp/<int:complaint_id>/', views.verify_otp, name='verify_otp'),
    path('success/<int:complaint_id>/', views.complaint_success, name='complaint_success'),
    
    # QR code generation
    path('qr/<str:station_code>/<int:platform_number>/', views.generate_station_qr, name='generate_station_qr'),
    
    # Station management
    path('station-setup/', views.station_setup, name='station_setup'),
    path('manage-station/', views.manage_station, name='manage_station'),
    path('download-qr-codes/<int:station_id>/', views.download_qr_codes, name='download_qr_codes'),
    
    # Complaint management
    path('update-status/<int:complaint_id>/', views.update_complaint_status, name='update_status'),
    path('assign-worker/<int:complaint_id>/', views.assign_worker, name='assign_worker'),
    
    # Utility pages
    path('success/', lambda request: render(request, 'complaints/success.html'), name='success'),
    path('error/', lambda request: render(request, 'complaints/error.html'), name='error'),
] 