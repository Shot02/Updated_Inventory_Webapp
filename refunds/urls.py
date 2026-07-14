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
    
    
    # sales api
    path('api/recent-sales/', views.recent_sales_api, name='recent_sales_api'),
    path('api/recent-sales-stats/', views.recent_sales_stats_api, name='recent_sales_stats_api'),
    path('api/sale-details/<int:pk>/', views.sale_details_api, name='sale_details_api'),
    path('api/search-all-sales/', views.search_all_sales_api, name='search_all_sales_api'),
    path('api/all-sales/', views.all_sales_api, name='all_sales_api'),
]