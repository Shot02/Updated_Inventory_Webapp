from django.urls import path
from . import views

urlpatterns = [
    path('', views.debtors_list, name='debtors_list'),
    path('detail/<str:customer_phone>/', views.debtor_detail, name='debtor_detail'),
    path('payment/<int:sale_id>/', views.record_payment, name='record_payment'),
    path('bulk-payment/', views.record_bulk_payment, name='record_bulk_payment'),
]