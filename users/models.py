from django.db import models
from django.contrib.auth.models import User
import uuid

# Create your models here.

class Profiles(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, blank=True)
    name = models.CharField(max_length=200, blank=True)
    email = models.EmailField(max_length=500)
    location = models.CharField(max_length=200, blank=True, null=True)
    profile_image = models.ImageField(null=True, blank=True, upload_to='profiles/', default='profiles/user-default.png')
    created = models.DateTimeField(auto_now_add=True)
    gender = models.CharField(max_length=200, null=True, blank=True)
    dateOfBirth = models.DateField(null=True, blank=True)
    id = models.UUIDField(default=uuid.uuid4, unique=True, 
                          primary_key=True, editable=False)
    
    def __str__(self):
        return str(self.user)
    

class Crew(models.Model):
    name = models.CharField(max_length=200)
    members = models.ManyToManyField(Profiles, through='CrewMembership', related_name='crews')
    id = models.UUIDField(default=uuid.uuid4, unique=True, 
                          primary_key=True, editable=False)

    def __str__(self):
        return str(self.name)


class CrewMembership(models.Model):
    ROLE_CHOICES = [('athlete', 'Athlete'), ('coach', 'Coach'), ('cox', 'Cox')]

    profile = models.ForeignKey(Profiles, on_delete=models.CASCADE, related_name='memberships')
    crew = models.ForeignKey(Crew, on_delete=models.CASCADE, related_name='memberships')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='athlete')

    class Meta:
        unique_together = ('profile', 'crew')

    def __str__(self):
        return f"{self.profile.name} - {self.crew.name} ({self.role})"


