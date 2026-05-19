from django.urls import path
from . import views

urlpatterns = [
    path('', views.agenda, name="agenda"),
    path('bodystats/', views.bodystats, name='bodystats'),
    path('bodystats/<uuid:pk>/edit/', views.editBodystats, name='edit-bodystats'),
    path('crews/', views.crewsPage, name='crews'),

    path('create-crew/', views.createCrew, name='create-crew'),
    path('crew/<str:pk>/', views.crewInfo, name='crew-info'),
    path('crew/<str:pk>/add-member/', views.addMemberToCrew, name='add-member-to-crew'),

    path('add-training/', views.createTraining, name='create-training'),
    path('edit-training/<str:pk>/', views.editTraining, name='edit-training'),
    path('delete-training/<str:pk>/', views.deleteTraining, name='delete-training'),
    path('training/<str:pk>/info/', views.trainingInfo, name='training-info'),
    path('training/<str:pk>/toggle-attendance/', views.toggleAttendance, name='toggle-attendance'),

    path('calendar/<uuid:token>.ics', views.personalCalendarFeed, name='personal-calendar-feed'),
    path('crew/<str:pk>/calendar/<uuid:token>.ics', views.crewCalendarFeed, name='crew-calendar-feed'),
]