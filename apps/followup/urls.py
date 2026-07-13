from django.urls import path

from . import views

app_name = 'followup'

urlpatterns = [
    path('', views.FollowUpListView.as_view(), name='list'),
    path('find/', views.find_person, name='find_person'),
    path('person/<str:person_id>/', views.timeline, name='timeline'),
    path('<int:pk>/close/', views.close_entry, name='close_entry'),
]
