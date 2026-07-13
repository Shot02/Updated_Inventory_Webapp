from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Authentication (inventoryApp)
    path('', include('inventoryApp.urls')),
    
    # Apps
    path('dashboard/', include('dashboard.urls')),
    path('branches/', include('branches.urls')),
    path('products/', include('products.urls')),
    path('sales/', include('sales.urls')),
    path('customers/', include('customers.urls')),
    path('suppliers/', include('suppliers.urls')),
    path('debtors/', include('debtors.urls')),
    path('refunds/', include('refunds.urls')),
    path('staff/', include('staff.urls')),
    path('select-branch/', include('select_branch.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)