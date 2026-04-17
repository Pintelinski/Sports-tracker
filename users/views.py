from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required

from .forms import CustomUserCreationForm, ProfileForm
from .models import Profiles

# Create your views here.

def landingPage(request):
    return render(request, 'users/landingPage.html')

def profiles(request):
    return render(request, 'users/profiles.html ')

def loginUser(request):
    page = 'login'

    if request.user.is_authenticated:
        return redirect('agenda')

    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        try:
            user = User.objects.get(username=username)
        except:
            messages.error(request, 'Username does not exist')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, 'User logged in succesfully')
            return redirect('agenda')

    return render(request, 'users/login.html')

@login_required(login_url='login')
def logoutUser(request):
    logout(request)
    messages.info(request, 'User was logged out!')
    return redirect('landingPage')

def registerUser(request):
    page = 'register'
    form = CustomUserCreationForm()

    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.username = user.username.lower()
            user.save()

            messages.success(request, 'User was created succesfully')

            login(request, user)
            return redirect('editProfile')
        
        else:
            messages.error(request, 'User creation failed')

    context = {'page': page, 'form':form}
    return render(request, 'users/register.html', context)


@login_required(login_url='login')
def profilePage(request):
    profile = request.user.profiles
    crews = profile.crews.all()

    context = {'profile': profile, 'crews': crews}
    return render(request, 'users/profilePage.html', context)


@login_required(login_url='login')
def editProfile(request):
    profile = request.user.profiles
    form = ProfileForm(instance=profile)

    # keep editing restricted to owner
    if profile.user != request.user:
        messages.error(request, 'You can only edit your own profile.')
        return redirect('agenda')


    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('profile')

    context = {'form': form, 'profile': profile}
    return render(request, 'users/editProfile.html', context)


def userProfile(request, pk):
    profile = Profiles.objects.get(id=pk)
    crews = profile.crews.all()

    context = {'profile': profile, 'crews': crews}
    return render(request, 'users/profilePage.html', context)