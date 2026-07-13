from django.contrib.auth import logout
from django.utils import timezone
from django.conf import settings
from datetime import datetime
from django.urls import reverse
from django.shortcuts import redirect
from django.contrib import messages

class SessionIdleTimeoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            current_path = request.path_info
            login_url = reverse('login')
            
            if current_path == login_url or current_path == reverse('logout'):
                return self.get_response(request)
            
            last_activity = request.session.get('last_activity')
            current_time = timezone.now()
            
            if last_activity:
                if isinstance(last_activity, str):
                    try:
                        if 'T' in last_activity:
                            last_activity = last_activity.replace('+00:00', '').replace('Z', '')
                            last_activity = datetime.fromisoformat(last_activity)
                        else:
                            last_activity = datetime.fromisoformat(last_activity)
                        
                        from django.utils.timezone import is_aware, make_aware
                        if not is_aware(last_activity) and is_aware(current_time):
                            last_activity = make_aware(last_activity)
                    except (ValueError, TypeError):
                        logout(request)
                        response = redirect(login_url + '?timeout=1')
                        return response
                
                idle_time = current_time - last_activity
                idle_minutes = idle_time.total_seconds() / 60
                
                if idle_minutes > getattr(settings, 'AUTO_LOGOUT_DELAY', 30):
                    logout(request)
                    response = redirect(login_url + '?timeout=1')
                    return response
            
            request.session['last_activity'] = current_time.isoformat()
        
        response = self.get_response(request)
        return response


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response


class BranchMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)
        
        if request.user.is_superuser:
            return self.get_response(request)
        
        if request.user.branch:
            request.current_branch = request.user.branch
        else:
            if request.path != reverse('select_branch') and not request.path.startswith('/admin/'):
                messages.warning(request, 'Please select a branch to continue.')
                return redirect('select_branch')
        
        response = self.get_response(request)
        return response