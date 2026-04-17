from django.urls import path
from . import views

urlpatterns = [
    path('', views.landingPage, name="landingPage"),
    path('profiles/', views.profiles, name="profiles"),
    path('login/', views.loginUser, name="login"),
    path('register/', views.registerUser, name="register"),
    path('logout/', views.logoutUser, name="logout"),
    
    path('profile/', views.profilePage, name="profile"),
    path('profile/<str:pk>/', views.userProfile, name="user-profile"),
    path('editProfile/', views.editProfile, name="editProfile"),
]