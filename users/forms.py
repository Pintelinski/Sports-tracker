from django import forms
from django.forms import ModelForm
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Crew, CrewMembership, Profiles


class CustomUserCreationForm(UserCreationForm):
    first_name = forms.CharField(required=True, max_length=200, label='Name')
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ['username','first_name', 'email', 'password1', 'password2']
    
    def __init__(self, *args, **kwargs):
        super(CustomUserCreationForm, self).__init__(*args, **kwargs)

        for name, field in self.fields.items():
            field.widget.attrs.update({'class': 'input'})

class CrewForm(ModelForm):
    role = forms.ChoiceField(choices=CrewMembership.ROLE_CHOICES)

    class Meta:
        model = Crew
        fields = ['name']

    
    def __init__(self, *args, **kwargs):
        super(CrewForm, self).__init__(*args, **kwargs)

        for name, field in self.fields.items():
            field.widget.attrs.update({'class': 'input'})

class ProfileForm(ModelForm):
    dateOfBirth = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), label='Date of Birth')
    gender = forms.ChoiceField(choices=[
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ], label='Gender')

    class Meta:
        model = Profiles
        fields = ['name', 'email', 'gender', 'dateOfBirth', 'location', 'profile_image']
        
    def __init__(self, *args, **kwargs):
        super(ProfileForm, self).__init__(*args, **kwargs)

        for name, field in self.fields.items():
            field.widget.attrs.update({'class': 'input'})