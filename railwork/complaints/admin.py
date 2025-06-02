from django.contrib import admin
from .models import Station, Complaint, OTPVerification

@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    list_display = ('name', 'station_code')
    search_fields = ('name', 'station_code')

@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ('complaint_number', 'station', 'platform_number', 'reporter_name', 'status', 'created_at')
    list_filter = ('status', 'station', 'created_at')
    search_fields = ('complaint_number', 'reporter_name', 'reporter_phone', 'description')
    readonly_fields = ('complaint_number', 'created_at', 'updated_at')

@admin.register(OTPVerification)
class OTPVerificationAdmin(admin.ModelAdmin):
    list_display = ('complaint', 'is_verified', 'created_at', 'attempts')
    list_filter = ('is_verified', 'created_at')
    readonly_fields = ('created_at',)
