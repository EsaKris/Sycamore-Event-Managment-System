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

    path('id-cards/', views.id_card_picker, name='id_cards'),
    path('id-cards/bulk-download/', views.id_card_bulk_download, name='id_card_bulk_download'),
    path('id-cards/<int:pk>/preview.png', views.id_card_preview, name='id_card_preview'),
    path('id-cards/<int:pk>/download.pdf', views.id_card_download, name='id_card_download'),
    path('id-cards/<int:pk>/badge-label/', views.id_card_set_badge_label, name='id_card_set_badge_label'),
]
