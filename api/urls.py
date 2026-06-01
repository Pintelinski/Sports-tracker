from django.urls import path
from . import views

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    # JWT
    path('users/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('users/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('users/me/', views.currentUser, name='current-user'),

    # Profiles
    path('profiles/', views.profileList, name='api-profile-list'),
    path('profiles/<uuid:pk>/', views.profileDetail, name='api-profile-detail'),

    # Crews
    path('crews/', views.crewList, name='api-crew-list'),
    path('crews/<uuid:pk>/', views.crewDetail, name='api-crew-detail'),

    # Crew memberships
    path('memberships/', views.membershipList, name='api-membership-list'),
    path('memberships/<int:pk>/', views.membershipDetail, name='api-membership-detail'),

    # Trainings
    path('trainings/', views.trainingList, name='api-training-list'),
    path('trainings/<uuid:pk>/', views.trainingDetail, name='api-training-detail'),

    # Attendance
    path('attendances/', views.attendanceList, name='api-attendance-list'),
    path('attendances/<int:pk>/', views.attendanceDetail, name='api-attendance-detail'),

    # Body stats (owner-private)
    path('bodystats/', views.bodyStatsList, name='api-bodystats-list'),
    path('bodystats/<uuid:pk>/', views.bodyStatsDetail, name='api-bodystats-detail'),
]
