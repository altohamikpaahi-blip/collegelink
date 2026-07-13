from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, DetailView, View
from django.views.generic.edit import CreateView
from django.urls import reverse_lazy
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from users.models import College  # استيراد الكلية لاستبعادها في الـ View
from .forms import DocumentForm
from .models import Document, Attachment, DocumentHistory, Department, DocumentForward

class DashboardView(LoginRequiredMixin, TemplateView):
    """عرض لوحة معلومات المراسلات وجلب الوارد والصادر الخاص بكل كلية وقسم مع ميزة البحث"""
    template_name = 'correspondence/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        query = self.request.GET.get('q', '').strip()

        if user.college:
            inbox_qs = Document.objects.filter(
                recipient_college=user.college, 
                status='sent'
            )
            outbox_qs = Document.objects.filter(
                sender_college=user.college
            )
            
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

            if user.department:
                dept_forwards_qs = DocumentForward.objects.filter(
                    department=user.department
                )
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
    """إنشاء وإرسال خطاب رسمي جديد مع تصفية قائمة المستقبلين وحماية برمجية ضد الانهيار"""
    model = Document
    form_class = DocumentForm
    template_name = 'correspondence/create_document.html'
    success_url = reverse_lazy('dashboard')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        user = self.request.user
        if user and user.college:
            form.fields['recipient_college'].queryset = College.objects.exclude(id=user.college.id)
        return form

    def form_valid(self, form):
        user = self.request.user
        
        # حماية برمجية: التحقق من انتساب الموظف الحالي لكلية ومنع انهيار الخادم
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
    """إنشاء وإرسال خطاب رد مع تعبئة الحقول تلقائياً وحماية برمجية ضد الانهيار"""
    model = Document
    form_class = DocumentForm
    template_name = 'correspondence/create_document.html'
    success_url = reverse_lazy('dashboard')

    def get_initial(self):
        initial = super().get_initial()
        parent_id = self.kwargs.get('parent_id')
        parent_doc = Document.objects.get(id=parent_id)
        
        initial['recipient_college'] = parent_doc.sender_college
        initial['title'] = f"رد على: {parent_doc.title}"
        return initial

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        user = self.request.user
        if user and user.college:
            form.fields['recipient_college'].queryset = College.objects.exclude(id=user.college.id)
        return form

    def form_valid(self, form):
        user = self.request.user
        parent_id = self.kwargs.get('parent_id')
        parent_doc = Document.objects.get(id=parent_id)
        
        # حماية برمجية للردود أيضاً لمنع الانهيار المفاجئ
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
    """عرض تفاصيل الخطاب مع التحقق من صلاحيات الأطراف لحماية الخصوصية"""
    model = Document
    template_name = 'correspondence/document_detail.html'
    context_object_name = 'document'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        user = self.request.user
        
        # حماية خصوصية الكليات
        if user.college not in [obj.sender_college, obj.recipient_college]:
            raise PermissionDenied("عذراً، ليس لديك الصلاحية للاطلاع على هذا الخطاب.")
            
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