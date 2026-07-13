from django.contrib import admin
from .models import Category, Product

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at']
    search_fields = ['name']

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'sku', 'price', 'quantity', 'category', 'supplier', 'branch']
    list_filter = ['category', 'supplier', 'branch', 'is_active']
    search_fields = ['name', 'sku']