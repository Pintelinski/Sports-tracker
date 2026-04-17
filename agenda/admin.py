from django.contrib import admin

# Register your models here.
from .models import Training, Attendance

admin.site.register(Training)
admin.site.register(Attendance)