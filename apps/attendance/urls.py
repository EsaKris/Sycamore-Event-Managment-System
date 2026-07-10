from django.urls import path

from . import views

app_name = 'attendance'

urlpatterns = [
    path('', views.AttendanceLogView.as_view(), name='log'),
    path('scanner/', views.scanner_view, name='scanner'),
    path('scan/', views.scan_api, name='scan_api'),
    path('sessions/create/', views.session_create, name='session_create'),
]
