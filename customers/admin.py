# customers/admin.py
from django.contrib import admin
from .models import Customer

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'customer_type', 'total_purchases', 'loyalty_points', 'is_active', 'branch']
    list_filter = ['customer_type', 'is_active', 'branch']
    search_fields = ['name', 'phone', 'email']
    readonly_fields = ['total_purchases', 'loyalty_points', 'last_purchase_date', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'phone', 'email', 'address', 'branch')
        }),
        ('Classification', {
            'fields': ('customer_type', 'is_active')
        }),
        ('Statistics', {
            'fields': ('total_purchases', 'loyalty_points', 'last_purchase_date')
        }),
        ('Additional', {
            'fields': ('notes',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )