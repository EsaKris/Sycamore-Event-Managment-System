from django.urls import path

from . import views

app_name = 'people'

urlpatterns = [
    path('<str:person_id>/qr.png', views.person_qr_image, name='qr_image'),
]
