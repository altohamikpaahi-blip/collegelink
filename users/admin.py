from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import College, Department, UserProfile

admin.site.register(College)
admin.site.register(Department)

@admin.register(UserProfile)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('معلومات الجامعة الإضافية', {'fields': ('role', 'college', 'department')}),
    )