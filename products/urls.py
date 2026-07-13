from django.urls import path
from . import views

urlpatterns = [
    path('', views.product_list, name='product_list'),
    path('add/', views.add_product, name='add_product'),
    path('edit/<int:pk>/', views.edit_product, name='edit_product'),
    path('delete/<int:pk>/', views.delete_product, name='delete_product'),
    path('api/search/', views.search_products_api, name='search_products_api'),
    path('api/expiring-products/', views.expiring_products_api, name='expiring_products_api'),
]