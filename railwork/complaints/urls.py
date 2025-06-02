from django.urls import path
from . import views
from django.shortcuts import render

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('submit/', views.submit_complaint, name='submit_complaint'),
    path('verify-otp/<int:complaint_id>/', views.verify_otp, name='verify_otp'),
    path('qr/<str:station_code>/<int:platform_number>/', views.generate_station_qr, name='generate_station_qr'),
    path('update-status/<int:complaint_id>/', views.update_complaint_status, name='update_status'),
    path('success/', lambda request: render(request, 'complaints/success.html'), name='success'),
    path('error/', lambda request: render(request, 'complaints/error.html'), name='error'),
    path('station-setup/', views.station_setup, name='station_setup'),
    path('download-qr-codes/<int:station_id>/', views.download_qr_codes, name='download_qr_codes'),
    path('assign-worker/<int:complaint_id>/', views.assign_worker, name='assign_worker'),
] 