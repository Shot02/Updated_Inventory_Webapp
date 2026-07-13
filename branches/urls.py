from django.urls import path
from . import views

urlpatterns = [
    path('', views.branch_list, name='branch_list'),
    path('add/', views.add_branch, name='add_branch'),
    path('edit/<int:pk>/', views.edit_branch, name='edit_branch'),
    path('delete/<int:pk>/', views.delete_branch, name='delete_branch'),
    path('switch/<int:branch_id>/', views.switch_branch, name='switch_branch'),
    path('clear/', views.clear_branch_selection, name='clear_branch_selection'),
]