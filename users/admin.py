from django.contrib import admin

# Register your models here.

from .models import Profiles, Crew, CrewMembership

admin.site.register(Profiles)
admin.site.register(Crew)
admin.site.register(CrewMembership)
