from django.contrib.auth import views as auth_views
from core.views import upload_request, dashboard_requests
from django.contrib import admin
from django.urls import path
from core import views
from django.conf import settings
from django.conf.urls.static import static
from core.views import staff_logout
"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('staff/login/', auth_views.LoginView.as_view(template_name='staff/login.html'), name='staff_login'),
    path('staff/logout/', staff_logout, name='staff_logout'),
    path('staff/dashboard/', dashboard_requests, name='dashboard_requests'),
    path('staff/process/<int:pk>/', views.process_request, name='process_request'),
    path('track/', views.track_request, name='track_request'),
    path('staff/request/<str:ref_code>/', views.admin_request_detail, name='admin_request_detail'),
    # Public upload page
    path('', upload_request, name='upload_request'),
]

from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)