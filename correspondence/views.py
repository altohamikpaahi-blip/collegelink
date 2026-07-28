from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, DetailView, View
from django.views.generic.edit import CreateView
from django.urls import reverse_lazy
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from users.models import College, UserProfile
from .forms import DocumentForm
from .models import Document, Attachment, DocumentHistory, Department, DocumentForward

class DashboardView(LoginRequiredMixin, TemplateView):
    """عرض لوحة معلومات المراسلات مع تصفية الخصوصية للبريد الوارد لشخص محدد"""
    template_name = 'correspondence/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        query = self.request.GET.get('q', '').strip()

        if user.college:
            # 1. تصفية صندوق الوارد المتقدمة لحماية الخصوصية
            if user.role in ['admin', 'dean', 'secretary']:
                inbox_qs = Document.objects.filter(recipient_college=user.college, status='sent')
            else:
                inbox_qs = Document.objects.filter(
                    recipient_college=user.college, 
                    status='sent'
                ).filter(Q(recipient_user=user) | Q(recipient_user__isnull=True))

            # 2. البريد الصادر للكلية
            outbox_qs = Document.objects.filter(sender_college=user.college)
            
            # تطبيق تصفية البحث
            if query:
                inbox_qs = inbox_qs.filter(
                    Q(title__icontains=query) | 
                    Q(content__icontains=query) | 
                    Q(reference_number__icontains=query)
                )
                outbox_qs = outbox_qs.filter(
                    Q(title__icontains=query) | 
                    Q(content__icontains=query) | 
                    Q(reference_number__icontains=query)
                )
                context['query'] = query

            context['inbox'] = inbox_qs.order_by('-created_at')
            context['outbox'] = outbox_qs.order_by('-created_at')

            # 3. الخطابات الموجهة لقسم المستخدم
            if user.department:
                dept_forwards_qs = DocumentForward.objects.filter(department=user.department)
                if query:
                    dept_forwards_qs = dept_forwards_qs.filter(
                        Q(document__title__icontains=query) | 
                        Q(document__content__icontains=query) | 
                        Q(document__reference_number__icontains=query)
                    )
                context['department_forwards'] = dept_forwards_qs.order_by('-timestamp')

        else:
            context['inbox'] = Document.objects.none()
            context['outbox'] = Document.objects.none()
            context['department_forwards'] = DocumentForward.objects.none()
            
        return context


class CreateDocumentView(LoginRequiredMixin, CreateView):
    """إنشاء وإرسال خطاب رسمي جديد مع تصفية قائمة المستقبلين برمجياً"""
    model = Document
    form_class = DocumentForm
    template_name = 'correspondence/create_document.html'
    success_url = reverse_lazy('dashboard')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        user = self.request.user
        if user and user.college:
            form.fields['recipient_college'].queryset = College.objects.exclude(id=user.college.id)
            form.fields['recipient_user'].queryset = UserProfile.objects.exclude(college=user.college)
        return form

    def form_valid(self, form):
        user = self.request.user
        if not getattr(user, 'college', None):
            raise PermissionDenied("عذراً، يجب ربط حسابك بكلية من لوحة التحكم أولاً لتتمكن من إرسال الخطابات الرسمية.")
            
        form.instance.sender = user
        form.instance.sender_college = user.college
        
        if 'send' in self.request.POST:
            form.instance.status = 'sent'
            form.instance.generate_reference()
        else:
            form.instance.status = 'draft'

        response = super().form_valid(form)
        
        attachment_file = self.request.FILES.get('attachment')
        if attachment_file:
            Attachment.objects.create(document=self.object, file=attachment_file)
        
        action_type = 'approve_send' if form.instance.status == 'sent' else 'create'
        DocumentHistory.objects.create(
            document=self.object,
            user=self.request.user,
            action=action_type,
            notes="تم إنشاء المعاملة إلكترونياً من الواجهة الرسمية"
        )
        
        return response


class ReplyDocumentView(LoginRequiredMixin, CreateView):
    """إنشاء وإرسال خطاب رد مع تعبئة الحقول تلقائياً وتصفيتها"""
    model = Document
    form_class = DocumentForm
    template_name = 'correspondence/create_document.html'
    success_url = reverse_lazy('dashboard')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        user = self.request.user
        if user and user.college:
            form.fields['recipient_college'].queryset = College.objects.exclude(id=user.college.id)
            form.fields['recipient_user'].queryset = UserProfile.objects.exclude(college=user.college)
        return form

    def get_initial(self):
        initial = super().get_initial()
        parent_id = self.kwargs.get('parent_id')
        parent_doc = Document.objects.get(id=parent_id)
        
        initial['recipient_college'] = parent_doc.sender_college
        initial['recipient_user'] = parent_doc.sender
        initial['title'] = f"رد على: {parent_doc.title}"
        return initial

    def form_valid(self, form):
        user = self.request.user
        parent_id = self.kwargs.get('parent_id')
        parent_doc = Document.objects.get(id=parent_id)
        
        if not getattr(user, 'college', None):
            raise PermissionDenied("عذراً، يجب ربط حسابك بكلية من لوحة التحكم أولاً لتتمكن من الرد على الخطابات الرسمية.")
            
        form.instance.parent = parent_doc
        form.instance.sender = user
        form.instance.sender_college = user.college
        
        if 'send' in self.request.POST:
            form.instance.status = 'sent'
            form.instance.generate_reference()
        else:
            form.instance.status = 'draft'

        response = super().form_valid(form)
        
        attachment_file = self.request.FILES.get('attachment')
        if attachment_file:
            Attachment.objects.create(document=self.object, file=attachment_file)
        
        DocumentHistory.objects.create(
            document=self.object,
            user=self.request.user,
            action='create',
            notes=f"تم إنشاء رد على الخطاب ذو الرقم المرجعي: {parent_doc.reference_number}"
        )
        return response


class DocumentDetailView(LoginRequiredMixin, DetailView):
    """عرض تفاصيل الخطاب مع ميزة تحديث مؤشر القراءة تلقائياً"""
    model = Document
    template_name = 'correspondence/document_detail.html'
    context_object_name = 'document'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        user = self.request.user
        
        # حماية خصوصية الكليات
        if user.college not in [obj.sender_college, obj.recipient_college]:
            raise PermissionDenied("عذراً، ليس لديك الصلاحية للاطلاع على هذا الخطاب.")
            
        # تحديث ذكي ومؤمن: إذا كان المستخدم الحالي ينتمي للكلية المستقبلة، والخطاب غير مقروء، يتم تحويله لمقروء فوراً وحفظه
        if user.college == obj.recipient_college and not obj.is_read:
            obj.is_read = True
            obj.save(update_fields=['is_read']) # تحديث حقل القراءة فقط في قاعدة البيانات لسرعة استجابة السيرفر
            
        return obj


class ForwardDocumentView(LoginRequiredMixin, View):
    """استقبال طلب التوجيه الداخلي للأقسام الأكاديمية"""
    def post(self, request, pk):
        document = get_object_or_404(Document, pk=pk)
        
        if request.user.college != document.recipient_college:
            raise PermissionDenied("لا تملك الصلاحية لتوجيه هذا الخطاب داخلياً.")
        
        dept_id = request.POST.get('department')
        notes = request.POST.get('notes', '').strip()
        
        if dept_id:
            department = get_object_or_404(Department, pk=dept_id)
            
            DocumentForward.objects.create(
                document=document,
                department=department,
                forwarded_by=request.user,
                notes=notes
            )
            
            DocumentHistory.objects.create(
                document=document,
                user=request.user,
                action='forward',
                notes=f"تم التوجيه للقسم الأكاديمي: {department.name}. بتوجيه: {notes if notes else 'لا يوجد توجيه خاص'}"
            )
            
        return redirect('document_detail', pk=pk)
