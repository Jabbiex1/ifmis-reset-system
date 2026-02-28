from django.contrib.auth import views as auth_views
from django.contrib import admin
from django.urls import path
from core.views import (
    upload_request,
    track_request,
    dashboard_requests,
    process_request,
    delete_request,
    bulk_delete_requests,
    admin_request_detail,
    serve_uploaded_file,
    staff_logout,
    audit_log_view,
)

urlpatterns = [
    path('admin/', admin.site.urls),

    # Public
    path('', upload_request, name='upload_request'),
    path('track/', track_request, name='track_request'),

    # Protected file serving
    path('uploads/<str:filename>', serve_uploaded_file, name='serve_uploaded_file'),

    # Staff auth
    path('staff/login/', auth_views.LoginView.as_view(template_name='staff/login.html'), name='staff_login'),
    path('staff/logout/', staff_logout, name='staff_logout'),

    # Staff portal
    path('staff/dashboard/', dashboard_requests, name='dashboard_requests'),
    path('staff/request/<str:ref_code>/', admin_request_detail, name='admin_request_detail'),
    path('staff/process/<int:pk>/', process_request, name='process_request'),
    path('staff/delete/<int:pk>/', delete_request, name='delete_request'),
    path('staff/bulk-delete/', bulk_delete_requests, name='bulk_delete_requests'),
    path('staff/audit/', audit_log_view, name='audit_log'),
]
