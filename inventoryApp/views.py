from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
import json
from .models import UserNotification
from branches.models import Branch
from sales.models import PendingCart

@csrf_exempt  # Add this decorator
def login_view(request):
    timeout = request.GET.get('timeout')
    if timeout:
        messages.warning(request, 'You have been logged out due to inactivity.')
    
    if request.user.is_authenticated:
        if request.user.role in ['admin', 'manager'] or request.user.is_superuser:
            return redirect('admin_dashboard')  # CHANGED
        else:
            return redirect('home')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            if not user.is_active:
                messages.error(request, 'Your account has been deactivated.')
                return render(request, 'login.html')
            
            login(request, user)
            request.session['last_activity'] = timezone.now().isoformat()
            request.session.set_expiry(settings.SESSION_COOKIE_AGE)
            PendingCart.objects.filter(staff=user).delete()
            
            if user.is_superuser or user.role == 'admin':
                if Branch.objects.count() == 0:
                    Branch.objects.create(
                        name='Ibadan Branch',
                        code='IBA',
                        address='Ibadan, Oyo State, Nigeria',
                        is_active=True
                    )
                    messages.info(request, 'Default Ibadan branch has been created.')
            
            messages.success(request, f'Welcome back, {user.username}!')
            
            if user.role in ['admin', 'manager'] or user.is_superuser:
                return redirect('admin_dashboard')  # CHANGED
            else:
                return redirect('home')
        else:
            messages.error(request, 'Invalid username or password')
    
    return render(request, 'login.html')

def logout_view(request):
    if request.method == 'POST':
        username = request.user.username
        request.session.flush()
        logout(request)
        response = redirect('login')
        response.delete_cookie('sessionid')
        response.delete_cookie('csrftoken')
        messages.success(request, f'You have been successfully logged out. See you next time!')
        return response
    else:
        logout(request)
        return redirect('login')

@login_required
@csrf_exempt
def refresh_session(request):
    if request.method == 'POST':
        request.session['last_activity'] = timezone.now().isoformat()
        request.session.set_expiry(settings.SESSION_COOKIE_AGE)
        return JsonResponse({
            'success': True,
            'message': 'Session refreshed successfully'
        })
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
@csrf_exempt
def mark_notifications_read(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            notification_type = data.get('notification_type')
            
            if notification_type in ['dashboard', 'debtors', 'refunds', 'sales']:
                UserNotification.mark_as_read(request.user, notification_type)
                return JsonResponse({'success': True})
            
            return JsonResponse({'success': False, 'error': 'Invalid notification type'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def notification_counts_api(request):
    return JsonResponse({
        'success': True,
        'dashboard_count': UserNotification.get_unread_count(request.user, 'dashboard'),
        'debtors_count': UserNotification.get_unread_count(request.user, 'debtors'),
        'refunds_count': UserNotification.get_unread_count(request.user, 'refunds'),
        'sales_count': UserNotification.get_unread_count(request.user, 'sales'),
        'total_count': UserNotification.get_unread_count(request.user),
    })