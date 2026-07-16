from django.urls import path

from . import views

app_name = 'people'

urlpatterns = [
    path('', views.PersonListView.as_view(), name='list'),
    path('<str:person_id>/', views.PersonDetailView.as_view(), name='detail'),
    path('<str:person_id>/qr.png', views.person_qr_image, name='qr_image'),
]
