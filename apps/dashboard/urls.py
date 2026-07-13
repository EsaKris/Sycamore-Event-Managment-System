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
    path('', views.DashboardHomeView.as_view(), name='home'),
]
