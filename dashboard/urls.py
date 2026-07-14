# dashboard/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.admin_dashboard, name='admin_dashboard'),
    
    path('api/search/<str:type>/', views.search_dashboard_api, name='search_dashboard_api'),
    path('api/profit-stats/', views.profit_stats_api, name='profit_stats_api'),
    path('mark-notifications-read/', views.mark_notifications_read, name='mark_notifications_read'),
]