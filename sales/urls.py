from django.urls import path
from . import views

urlpatterns = [
    path('home/', views.home, name='home'),
    path('api/search-products/', views.search_products_api, name='search_products_api'), 
    path('receipt/<int:sale_id>/', views.view_receipt, name='view_receipt'),
    path('history/', views.sale_history, name='sale_history'),
    path('api/sales-history/', views.sale_history_search_api, name='sale_history_search_api'),
    path('api/process-sale/', views.process_sale, name='process_sale'),
    path('api/save-cart/', views.save_cart, name='save_cart'),
    path('api/load-saved-cart/<int:cart_id>/', views.load_saved_cart, name='load_saved_cart'),
    path('api/delete-saved-cart/<int:cart_id>/', views.delete_saved_cart, name='delete_saved_cart'),
    path('saved-carts/', views.saved_carts_list, name='saved_carts_list'),
    path('saved-cart/<int:cart_id>/', views.view_saved_cart, name='view_saved_cart'),
    path('api/recent-sales-stats/', views.recent_sales_stats_api, name='recent_sales_stats'),
    path('api/recent-sales/', views.recent_sales_api, name='recent_sales'),
    path('api/sale-details/<int:pk>/', views.sale_details_api, name='sale_details_api'),
    path('api/profit-stats/', views.profit_stats_api, name='profit_stats_api'),
]