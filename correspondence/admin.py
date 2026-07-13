from django.contrib import admin
from .models import Document, Attachment, DocumentHistory

class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 1

class DocumentHistoryInline(admin.TabularInline):
    model = DocumentHistory
    extra = 0
    readonly_fields = ('user', 'action', 'notes', 'timestamp')

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'sender_college', 'recipient_college', 'status', 'reference_number', 'created_at')
    list_filter = ('status', 'sender_college', 'recipient_college')
    search_fields = ('title', 'content', 'reference_number')
    inlines = [AttachmentInline, DocumentHistoryInline]

    def save_model(self, request, obj, form, change):
        # توليد الرقم المرجعي تلقائياً عند تغيير الحالة إلى "تم الإرسال"
        if obj.status == 'sent' and not obj.reference_number:
            obj.generate_reference()
        super().save_model(request, obj, form, change)