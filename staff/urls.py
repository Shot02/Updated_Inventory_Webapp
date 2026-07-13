from django.urls import path
from . import views

urlpatterns = [
    path('', views.staff_list, name='staff_list'),
    path('register/', views.register_staff, name='register_staff'),
    path('edit/', views.edit_staff, name='edit_staff'),
    path('delete/<int:pk>/', views.delete_staff, name='delete_staff'),
]