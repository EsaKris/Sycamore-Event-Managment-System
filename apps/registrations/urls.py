from django.urls import path

from . import views

app_name = 'registrations'

urlpatterns = [
    path('', views.RegistrationListView.as_view(), name='list'),
    path('<int:pk>/', views.RegistrationDetailView.as_view(), name='detail'),

    path('new/', views.start, name='start'),
    path('new/search/', views.search, name='search'),
    path('new/search/use-match/', views.use_match, name='use_match'),
    path('new/search/register-as-new/', views.register_as_new, name='register_as_new'),
    path('new/details/', views.details, name='details'),
    path('new/success/<int:pk>/', views.success, name='success'),
]
