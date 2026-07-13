from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from correspondence.views import DashboardView, CreateDocumentView, DocumentDetailView, ReplyDocumentView, ForwardDocumentView

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # واجهات تسجيل الدخول والخروج
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    # واجهات المراسلات الأساسية
    path('document/new/', CreateDocumentView.as_view(), name='create_document'),
    path('document/<int:parent_id>/reply/', ReplyDocumentView.as_view(), name='reply_document'),
    path('document/<int:pk>/forward/', ForwardDocumentView.as_view(), name='forward_document'),
    path('document/<int:pk>/', DocumentDetailView.as_view(), name='document_detail'), 
    
    # الصفحة الرئيسية (لوحة المعلومات)
    path('', DashboardView.as_view(), name='dashboard'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)