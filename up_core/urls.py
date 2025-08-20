from django.urls import path
from up_core import views

urlpatterns = [
    path('api/daemon/status/', views.daemon_status, name='daemon_status'),
    path('api/system/health/', views.system_health, name='system_health'),
    path('api/system/security/', views.system_security, name='system_security'),
]