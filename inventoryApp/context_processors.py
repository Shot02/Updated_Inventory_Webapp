from .models import UserNotification
from django.conf import settings
from branches.models import Branch

def notifications(request):
    if request.user.is_authenticated:
        return {
            'unread_dashboard_count': UserNotification.get_unread_count(
                request.user, 'dashboard'
            ),
            'unread_debtors_count': UserNotification.get_unread_count(
                request.user, 'debtors'
            ),
            'unread_refunds_count': UserNotification.get_unread_count(
                request.user, 'refunds'
            ),
            'unread_sales_count': UserNotification.get_unread_count(
                request.user, 'sales'
            ),
            'total_unread_count': UserNotification.get_unread_count(request.user),
        }
    return {}

def session_timeout(request):
    return {
        'session_timeout': getattr(settings, 'AUTO_LOGOUT_DELAY', 30),
    }

def all_branches(request):
    if request.user.is_authenticated:
        branches = Branch.objects.filter(is_active=True).order_by('name')
        return {'all_branches': branches}
    return {}