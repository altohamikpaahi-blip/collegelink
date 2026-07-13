import os
from django.db import models
from django.conf import settings
from users.models import College, Department  # استيراد القسم الكلي أيضاً

class Document(models.Model):
    STATUS_CHOICES = [
        ('draft', 'مسودة'),
        ('pending', 'قيد المراجعة والاعتماد'),
        ('sent', 'تم الإرسال (صادر)'),
        ('archived', 'تمت الأرشفة (مغلق)'),
    ]

    title = models.CharField(max_length=255, verbose_name="عنوان الخطاب")
    content = models.TextField(verbose_name="محتوى الخطاب")
    
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.PROTECT, 
        related_name='sent_documents', 
        verbose_name="المنشئ"
    )
    sender_college = models.ForeignKey(
        College, 
        on_delete=models.PROTECT, 
        related_name='outgoing_documents', 
        verbose_name="الكلية المرسلة"
    )
    
    recipient_college = models.ForeignKey(
        College, 
        on_delete=models.PROTECT, 
        related_name='incoming_documents', 
        verbose_name="الكلية المستقبلة"
    )
    
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='draft', 
        verbose_name="حالة الخطاب"
    )
    
    reference_number = models.CharField(
        max_length=50, 
        unique=True, 
        null=True, 
        blank=True, 
        verbose_name="الرقم المرجعي (الصادر)"
    )
    
    # حقل الربط بالخطاب الأصلي لتمكين الردود
    parent = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='replies', 
        verbose_name="الخطاب الأصلي"
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاريخ التحديث")

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"

    def generate_reference(self):
        """توليد رقم مرجعي تلقائي فريد عند تغيير حالة الخطاب إلى 'تم الإرسال'"""
        import datetime
        if not self.reference_number and self.status == 'sent':
            year = datetime.datetime.now().year
            count = Document.objects.filter(
                sender_college=self.sender_college,
                status='sent',
                created_at__year=year
            ).count() + 1
            
            self.reference_number = f"{self.sender_college.code}-{self.recipient_college.code}-{year}-{count:04d}"


class Attachment(models.Model):
    document = models.ForeignKey(
        Document, 
        on_delete=models.CASCADE, 
        related_name='attachments', 
        verbose_name="الخطاب"
    )
    file = models.FileField(upload_to='attachments/%Y/%m/%d/', verbose_name="الملف المرفق")
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الرفع")

    def __str__(self):
        return os.path.basename(self.file.name)


class DocumentHistory(models.Model):
    ACTION_CHOICES = [
        ('create', 'إنشاء مسودة'),
        ('request_approval', 'طلب اعتماد دائم'),
        ('approve_send', 'اعتماد وإرسال'),
        ('forward', 'توجيه / تحويل داخلي'),
        ('archive', 'أرشفة وإغلاق المعاملة'),
    ]
    
    document = models.ForeignKey(
        Document, 
        on_delete=models.CASCADE, 
        related_name='history', 
        verbose_name="الخطاب"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        verbose_name="المسؤول عن الإجراء"
    )
    action = models.CharField(max_length=30, choices=ACTION_CHOICES, verbose_name="الإجراء")
    notes = models.TextField(null=True, blank=True, verbose_name="ملاحظات / توجيهات")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="الوقت والطلب")

    def __str__(self):
        return f"{self.document.title} - {self.get_action_display()} بواسطة {self.user}"


class DocumentForward(models.Model):
    """نموذج لتخزين حركات توجيه الخطابات للأقسام الأكاديمية"""
    document = models.ForeignKey(
        Document, 
        on_delete=models.CASCADE, 
        related_name='forwards', 
        verbose_name="الخطاب"
    )
    department = models.ForeignKey(
        Department, 
        on_delete=models.CASCADE, 
        related_name='received_forwards', 
        verbose_name="القسم الأكاديمي"
    )
    forwarded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        verbose_name="الموجّه"
    )
    notes = models.TextField(null=True, blank=True, verbose_name="ملاحظات / توجيهات العميد")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="وقت التوجيه")

    def __str__(self):
        return f"توجيه {self.document.title} إلى {self.department.name}"