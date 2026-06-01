from rest_framework import serializers
from django.contrib.auth.models import User

from users.models import Profiles, Crew, CrewMembership
from agenda.models import Training, Attendance, BodyStats


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']


class ProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Profiles
        fields = [
            'id', 'username', 'name', 'email', 'location',
            'profile_image', 'gender', 'dateOfBirth', 'created',
        ]
        read_only_fields = ['id', 'created', 'username']


class CrewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Crew
        fields = ['id', 'name']
        read_only_fields = ['id']


class CrewMembershipSerializer(serializers.ModelSerializer):
    profile_name = serializers.CharField(source='profile.name', read_only=True)
    crew_name = serializers.CharField(source='crew.name', read_only=True)

    class Meta:
        model = CrewMembership
        fields = ['id', 'profile', 'crew', 'role', 'profile_name', 'crew_name']


class TrainingSerializer(serializers.ModelSerializer):
    crew_name = serializers.CharField(source='crew.name', read_only=True)

    class Meta:
        model = Training
        fields = [
            'id', 'title', 'datetime', 'duration', 'description',
            'intensity', 'crew', 'crew_name', 'created',
        ]
        read_only_fields = ['id', 'created', 'crew_name']


class AttendanceSerializer(serializers.ModelSerializer):
    athlete_name = serializers.CharField(source='athlete.name', read_only=True)
    training_title = serializers.CharField(source='training.title', read_only=True)

    class Meta:
        model = Attendance
        fields = ['id', 'training', 'athlete', 'status', 'athlete_name', 'training_title']


class BodyStatsSerializer(serializers.ModelSerializer):
    class Meta:
        model = BodyStats
        fields = [
            'id', 'profile', 'date', 'weight',
            'resting_heartrate', 'hrv', 'body_battery',
        ]
        read_only_fields = ['id', 'profile']
