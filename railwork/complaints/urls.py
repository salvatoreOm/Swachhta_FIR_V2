from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('qr/<str:station_code>/<int:platform_number>/', views.generate_station_qr, name='generate_qr'),
    path('submit/', views.submit_complaint, name='submit_complaint'),
    path('verify/<int:complaint_id>/', views.verify_otp, name='verify_otp'),
    path('update-status/<int:complaint_id>/', views.update_complaint_status, name='update_status'),
] 