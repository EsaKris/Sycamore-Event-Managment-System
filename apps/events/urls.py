from django.urls import path

from . import views

app_name = 'events'

urlpatterns = [
    path('', views.EventListView.as_view(), name='list'),
    path('new/', views.event_form, name='create'),
    path('<int:pk>/', views.EventDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.event_form, name='edit'),
    path('<int:pk>/toggle-registration/', views.event_toggle_registration, name='toggle_registration'),
    path('<int:pk>/set-status/', views.event_set_status, name='set_status'),
]
