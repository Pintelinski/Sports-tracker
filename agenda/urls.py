from django.urls import path
from . import views

urlpatterns = [
    path('', views.agenda, name="agenda"),
    path('bodystats/', views.bodystats, name='bodystats'),
    path('crews/', views.crewsPage, name='crews'),

    path('create-crew/', views.createCrew, name='create-crew'),
    path('crew/<str:pk>/', views.crewInfo, name='crew-info'),
    path('crew/<str:pk>/add-member/', views.addMemberToCrew, name='add-member-to-crew'),

    path('add-training/', views.createTraining, name='create-training'),

]