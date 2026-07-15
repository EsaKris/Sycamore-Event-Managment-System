from django.urls import path

from . import views

app_name = 'departments'

urlpatterns = [
    path('', views.DepartmentListView.as_view(), name='list'),
    path('new/', views.department_form, name='create'),
    path('<int:pk>/edit/', views.department_form, name='edit'),
    path('<int:pk>/toggle-active/', views.department_toggle_active, name='toggle_active'),
]
