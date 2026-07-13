from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('', views.AdministratorListView.as_view(), name='list'),
    path('find-person/', views.FindPersonToPromoteView.as_view(), name='find_person'),
    path('make-administrator/<str:person_id>/', views.make_administrator, name='make_administrator'),
    path('credentials/', views.credentials_reveal, name='credentials'),
    path('<int:user_id>/toggle-active/', views.toggle_active, name='toggle_active'),
    path('<int:user_id>/reset-password/', views.reset_password, name='reset_password'),
    path('<int:user_id>/change-role/', views.change_role, name='change_role'),
]
