from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('role', 'phone', 'address', 'branch')}),
    )
    list_display = ['username', 'email', 'role', 'phone', 'branch', 'is_active']
    list_filter = ['role', 'is_active', 'branch']