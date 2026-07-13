from django.contrib.auth.models import AbstractUser
from django.db import models

class College(models.Model):
    name = models.CharField(max_length=255, verbose_name="اسم الكلية")
    code = models.CharField(max_length=10, unique=True, verbose_name="رمز الكلية")

    # الدالة السحرية لإظهار الاسم الحقيقي للكلية في لوحة التحكم والقوائم
    def __str__(self):
        return self.name


class Department(models.Model):
    college = models.ForeignKey(
        College, 
        on_delete=models.CASCADE, 
        related_name='departments', 
        verbose_name="الكلية"
    )
    name = models.CharField(max_length=255, verbose_name="اسم القسم")

    # الدالة السحرية لإظهار اسم القسم مقروناً برمز الكلية التابع لها
    def __str__(self):
        return f"{self.name} - {self.college.code}"


class UserProfile(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'مدير النظام'),
        ('dean', 'عميد الكلية'),
        ('head_of_dept', 'رئيس القسم'),
        ('secretary', 'سكرتير'),
        ('staff', 'موظف'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='staff', verbose_name="الدور الوظيفي")
    college = models.ForeignKey(College, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="الكلية المنتسب إليها")
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="القسم المنتسب إليه")