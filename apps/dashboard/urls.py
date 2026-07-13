from django.urls import path

from . import views

app_name = 'dashboard'

urlpatterns = [
    path('login/', views.AdminLoginView.as_view(), name='login'),
    path('logout/', views.AdminLogoutView.as_view(), name='logout'),
    path('change-password/', views.change_password, name='change_password'),
    path('', views.DashboardHomeView.as_view(), name='home'),
]
