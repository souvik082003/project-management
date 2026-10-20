from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'username', 'name', 'role', 'department', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_superuser', 'department')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('PMS Information', {'fields': ('name', 'role', 'department', 'roll_no', 'employee_id')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('PMS Information', {'fields': ('name', 'role', 'department', 'roll_no', 'employee_id')}),
    )
