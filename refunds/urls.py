from django.urls import path
from . import views

urlpatterns = [
    path('', views.refund_list, name='refund_list'),
    path('requests/', views.refund_requests_list, name='refund_requests_list'),
    path('create/', views.create_refund_request, name='create_refund_request'),
    path('approve/<int:pk>/', views.approve_refund_request, name='approve_refund_request'),
    path('decline/<int:pk>/', views.decline_refund_request, name='decline_refund_request'),
    path('delete/<int:pk>/', views.delete_refund_request, name='delete_refund_request'),
    path('api/stats/', views.get_refund_stats, name='get_refund_stats'),
    path('api/details/<int:pk>/', views.refund_details_api, name='refund_details_api'),
]