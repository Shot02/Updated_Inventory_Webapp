# select_branch/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.select_branch, name='select_branch'),
]