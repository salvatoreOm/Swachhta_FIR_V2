from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import City, Station, LocationType, PlatformLocation, Complaint, ComplaintPhoto, OTPVerification

class CityAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'admin')
    search_fields = ('name', 'code')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            return qs.filter(admin=request.user)
        return qs

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "admin" and not request.user.is_superuser:
            kwargs["queryset"] = User.objects.filter(id=request.user.id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

class PlatformLocationInline(admin.TabularInline):
    model = PlatformLocation
    extra = 0
    readonly_fields = ('qr_code_preview',)
    fields = ('platform_number', 'location_type', 'qr_code_preview')

    def qr_code_preview(self, obj):
        if obj.qr_code:
            return format_html('<a href="{}" target="_blank"><img src="{}" width="100" height="100" /></a>', 
                             obj.qr_code.url, obj.qr_code.url)
        return "No QR code generated yet"
    qr_code_preview.short_description = _('QR Code')

class StationAdmin(admin.ModelAdmin):
    list_display = ('name', 'station_code', 'city', 'total_platforms')
    search_fields = ('name', 'station_code')
    list_filter = ('city',)
    inlines = [PlatformLocationInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            return qs.filter(city__admin=request.user)
        return qs

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "city" and not request.user.is_superuser:
            kwargs["queryset"] = City.objects.filter(admin=request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

class ComplaintAdmin(admin.ModelAdmin):
    list_display = ('complaint_number', 'station', 'get_platform_info', 'status', 'created_at', 'is_verified', 'assigned_worker')
    list_filter = ('status', 'is_verified', 'station__city', 'station')
    search_fields = ('complaint_number', 'reporter_name', 'reporter_phone', 'assigned_worker')
    readonly_fields = ('complaint_number', 'created_at', 'updated_at')

    def get_platform_info(self, obj):
        if obj.platform_location:
            return f"Platform {obj.platform_location.platform_number} - {obj.platform_location.location_type.name}"
        return "-"
    get_platform_info.short_description = _('Platform Location')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            return qs.filter(station__city__admin=request.user)
        return qs

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if not request.user.is_superuser:
            if db_field.name == "station":
                kwargs["queryset"] = Station.objects.filter(city__admin=request.user)
            elif db_field.name == "platform_location":
                kwargs["queryset"] = PlatformLocation.objects.filter(station__city__admin=request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

admin.site.register(City, CityAdmin)
admin.site.register(Station, StationAdmin)
admin.site.register(LocationType)
admin.site.register(Complaint, ComplaintAdmin)
admin.site.register(ComplaintPhoto)
admin.site.register(OTPVerification)
