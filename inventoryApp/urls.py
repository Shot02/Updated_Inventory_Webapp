from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('api/refresh-session/', views.refresh_session, name='refresh_session'),
    path('api/notification-counts/', views.notification_counts_api, name='notification_counts_api'),
    path('mark-notifications-read/', views.mark_notifications_read, name='mark_notifications_read'),
]