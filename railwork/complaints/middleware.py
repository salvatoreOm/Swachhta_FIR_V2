from django.shortcuts import redirect
from django.urls import reverse
from django.http import HttpResponseForbidden
from django.contrib import messages
from django.utils.translation import gettext as _

class AdminAccessMiddleware:
    """
    Middleware to prevent regular users from accessing the admin panel
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if the request is for admin panel
        if request.path.startswith('/admin/'):
            # Allow superusers and staff to access admin
            if request.user.is_authenticated and (request.user.is_superuser or request.user.is_staff):
                pass  # Allow access
            # Prevent regular authenticated users from accessing admin
            elif request.user.is_authenticated:
                messages.error(request, _('You do not have permission to access the admin panel.'))
                return redirect('user_dashboard')
            # Allow unauthenticated users to access login page
            elif '/admin/login/' in request.path:
                pass  # Allow access to admin login
            else:
                # Redirect unauthenticated users to user login
                return redirect('user_login')
        
        response = self.get_response(request)
        return response 