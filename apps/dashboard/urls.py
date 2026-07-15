from django.urls import path

from . import views

app_name = 'dashboard'

urlpatterns = [
    path('login/', views.AdminLoginView.as_view(), name='login'),
    path('logout/', views.AdminLogoutView.as_view(), name='logout'),
    path('change-password/', views.change_password, name='change_password'),
    path('search/', views.search_page, name='search'),
    path('search/api/', views.search_api, name='search_api'),
    path('reports/', views.reports_index, name='reports'),
    path('reports/export/', views.report_export, name='report_export'),
    path('analytics/', views.analytics_view, name='analytics'),
    path('activity-logs/', views.activity_logs, name='activity_logs'),
    path('notifications/', views.notifications_page, name='notifications'),
    path('notifications/api/', views.notifications_dropdown_api, name='notifications_api'),
    path('notifications/<int:pk>/read/', views.notification_mark_read, name='notification_mark_read'),
    path('notifications/mark-all-read/', views.notification_mark_all_read, name='notification_mark_all_read'),
    path('settings/', views.SettingsView.as_view(), name='settings'),
    path('', views.DashboardHomeView.as_view(), name='home'),
]
