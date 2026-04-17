from django.db import models
import uuid
from users.models import Profiles, Crew

# Create your models here.
    
class Training(models.Model):
    INTENSITY_CHOICES = [('T1', 'Warm up'), ('T2', 'Easy'), ('T3', 'Aerobic'), ('T4', 'Threshold'), ('T5', 'Maximum')]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    datetime = models.DateTimeField()
    duration = models.DurationField()
    description = models.TextField(blank=True, null=True)
    intensity = models.CharField(max_length=10, choices=INTENSITY_CHOICES)
    crew = models.ForeignKey(Crew, on_delete=models.CASCADE, related_name='trainings')
    created = models.DateTimeField(auto_now_add=True)
    id = models.UUIDField(default=uuid.uuid4, unique=True, primary_key=True, editable=False)

    def __str__(self):
        return str(self.title)


class Attendance(models.Model):
    STATUS_CHOICES = [('present', 'Present'), ('absent', 'Absent'), ('pending', 'Pending')]

    training = models.ForeignKey(Training, on_delete=models.CASCADE, related_name='attendances')
    athlete = models.ForeignKey(Profiles, on_delete=models.CASCADE, related_name='attendances')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')

    class Meta:
        unique_together = ('training', 'athlete')

    def __str__(self):
        return f"{self.athlete.name} - {self.training.title} ({self.status})"