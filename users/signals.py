from django.db.models.signals import post_save, post_delete
from django.contrib.auth.models import User

from .models import Profiles, CrewMembership, Crew


def createProfile(sender, instance, created, **kwargs):
    if created:
        user = instance
        Profiles.objects.create(
            user=user,
            name=user.first_name,
            email=user.email,
        )


def createCrewMembership(sender, instance, created, **kwargs):
    crew = instance
    profile = getattr(crew, '_pending_member_profile', None)
    role = getattr(crew, '_pending_member_role', 'athlete')

    if profile is None:
        return

    CrewMembership.objects.create(
        profile=profile,
        crew=crew,
        role=role,
    )


post_save.connect(createProfile, sender=User)
post_save.connect(createCrewMembership, sender=Crew)