from django.urls import path

from . import views

app_name = 'campaigns'

urlpatterns = [
    path('', views.CampaignListView.as_view(), name='list'),
    path('new/', views.campaign_form, name='create'),
    path('<int:pk>/', views.campaign_detail, name='detail'),
    path('<int:pk>/edit/', views.campaign_form, name='edit'),
    path('<int:pk>/sync/', views.campaign_sync, name='sync'),
    path('<int:pk>/send/', views.campaign_send, name='send'),

    path('templates/', views.TemplateListView.as_view(), name='templates'),
    path('templates/new/', views.template_form, name='template_create'),
    path('templates/<int:pk>/edit/', views.template_form, name='template_edit'),

    path('track/<uuid:token>.gif', views.track_open, name='track_open'),
]
