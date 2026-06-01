"""
REST API for the Sportstracker app.

All endpoints require a valid JWT in the Authorization header
(`Authorization: Bearer <access-token>`). Mint a token with
POST /api/users/token/ and refresh it with POST /api/users/token/refresh/.

Function-based @api_view style — same as the rest of the project's view layout.

Read paths use `Model.objects.get(...)` with explicit try/except.
Write paths use the same `ModelForm`s as `users/views.py` and `agenda/views.py`
(`ProfileForm`, `CrewForm`, `TrainingForm`, `BodyStatsForm`) so the API and the
HTML views stay in lockstep.

Authorization rules mirror what the UI enforces:
- BodyStats are private — only the owner can read or write their rows.
- CrewMembership creation requires the requester to already be in the crew.
- Trainings can only be created/edited by members of the training's crew.
- Attendance can only be set by the athlete it belongs to.
- Profiles are visible to any authenticated user; only the owner can edit theirs.
"""

from datetime import datetime, timedelta

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django.utils import timezone

from users.models import Profiles, Crew, CrewMembership
from users.forms import CrewForm, ProfileForm
from agenda.models import Training, Attendance, BodyStats
from agenda.forms import TrainingForm, BodyStatsForm

from .serializer import (
    UserSerializer,
    ProfileSerializer,
    CrewSerializer,
    CrewMembershipSerializer,
    TrainingSerializer,
    AttendanceSerializer,
    BodyStatsSerializer,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _requesterProfile(request):
    """Return (profile, error_response). Mirrors the try/except pattern
    used everywhere in the existing views.py files."""
    try:
        return Profiles.objects.get(user=request.user), None
    except Profiles.DoesNotExist:
        return None, Response(
            {'detail': 'No profile attached to the current user.'},
            status=status.HTTP_400_BAD_REQUEST,
        )


def _parseDecimal(raw):
    return raw if raw not in (None, '') else None


def _parseInt(raw):
    return int(raw) if raw not in (None, '') else None


# ---------------------------------------------------------------------------
# Current user (kept from the original course-reference view)
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def currentUser(request):
    serializer = UserSerializer(request.user)
    return Response(serializer.data)


# ---------------------------------------------------------------------------
# Profiles — uses ProfileForm for updates, matching editProfile
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profileList(request):
    profiles = Profiles.objects.all()
    return Response(ProfileSerializer(profiles, many=True).data)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def profileDetail(request, pk):
    try:
        profile = Profiles.objects.get(id=pk)
    except Profiles.DoesNotExist:
        return Response({'detail': 'Profile not found.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(ProfileSerializer(profile).data)

    if profile.user_id != request.user.id:
        return Response(
            {'detail': 'You can only modify your own profile.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == 'DELETE':
        profile.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    form = ProfileForm(request.data, request.FILES, instance=profile)
    if form.is_valid():
        form.save()
        return Response(ProfileSerializer(profile).data)
    return Response(form.errors, status=status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# Crews — create uses CrewForm with the same _pending_member trick
# as createCrew does in agenda/views.py
# ---------------------------------------------------------------------------

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def crewList(request):
    if request.method == 'GET':
        crews = Crew.objects.all()
        return Response(CrewSerializer(crews, many=True).data)

    requester, err = _requesterProfile(request)
    if err:
        return err

    form = CrewForm(request.data)
    if form.is_valid():
        crew = form.save(commit=False)
        crew._pending_member_profile = requester
        crew._pending_member_role = form.cleaned_data['role']
        crew.save()
        return Response(CrewSerializer(crew).data, status=status.HTTP_201_CREATED)
    return Response(form.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def crewDetail(request, pk):
    try:
        crew = Crew.objects.get(id=pk)
    except Crew.DoesNotExist:
        return Response({'detail': 'Crew not found.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(CrewSerializer(crew).data)

    requester, err = _requesterProfile(request)
    if err:
        return err

    if not CrewMembership.objects.filter(profile=requester, crew=crew).exists():
        return Response(
            {'detail': 'Only members of this crew may modify it.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == 'DELETE':
        crew.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # Direct field update — there's no edit-crew form in the existing UI,
    # so we follow the editBodystats pattern (read fields off the request).
    name = request.data.get('name')
    if name in (None, ''):
        return Response({'name': ['This field is required.']}, status=status.HTTP_400_BAD_REQUEST)
    crew.name = name
    crew.save()
    return Response(CrewSerializer(crew).data)


# ---------------------------------------------------------------------------
# CrewMembership — create uses the same _pending_member trick as
# addMemberToCrew, so the post_save signal that wires up the membership
# fires the same way it does for the HTML view.
# ---------------------------------------------------------------------------

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def membershipList(request):
    if request.method == 'GET':
        return Response(CrewMembershipSerializer(CrewMembership.objects.all(), many=True).data)

    requester, err = _requesterProfile(request)
    if err:
        return err

    crew_id = request.data.get('crew')
    profile_id = request.data.get('profile')
    role = request.data.get('role', 'athlete')

    valid_roles = {value for value, _ in CrewMembership.ROLE_CHOICES}
    if role not in valid_roles:
        return Response({'role': ['Invalid role.']}, status=status.HTTP_400_BAD_REQUEST)

    try:
        crew = Crew.objects.get(id=crew_id)
    except Crew.DoesNotExist:
        return Response({'crew': ['Crew not found.']}, status=status.HTTP_400_BAD_REQUEST)

    try:
        profile = Profiles.objects.get(id=profile_id)
    except Profiles.DoesNotExist:
        return Response({'profile': ['Profile not found.']}, status=status.HTTP_400_BAD_REQUEST)

    if not CrewMembership.objects.filter(profile=requester, crew=crew).exists():
        return Response(
            {'detail': 'Only members of this crew may add new members.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    crew._pending_member_profile = profile
    crew._pending_member_role = role
    crew.save()

    membership = CrewMembership.objects.get(profile=profile, crew=crew)
    return Response(
        CrewMembershipSerializer(membership).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def membershipDetail(request, pk):
    try:
        membership = CrewMembership.objects.get(id=pk)
    except CrewMembership.DoesNotExist:
        return Response({'detail': 'Membership not found.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(CrewMembershipSerializer(membership).data)

    requester, err = _requesterProfile(request)
    if err:
        return err

    if not CrewMembership.objects.filter(profile=requester, crew=membership.crew).exists():
        return Response(
            {'detail': 'Only members of this crew may modify its memberships.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == 'DELETE':
        membership.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    role = request.data.get('role')
    if role is not None:
        valid_roles = {value for value, _ in CrewMembership.ROLE_CHOICES}
        if role not in valid_roles:
            return Response({'role': ['Invalid role.']}, status=status.HTTP_400_BAD_REQUEST)
        membership.role = role
        membership.save()
    return Response(CrewMembershipSerializer(membership).data)


# ---------------------------------------------------------------------------
# Trainings — create/update use TrainingForm and the same date/time/duration
# split as createTraining and editTraining in agenda/views.py
# ---------------------------------------------------------------------------

def _saveTrainingFromForm(form):
    """Mirror the body of createTraining/editTraining — combine the form's
    split date/start_time/duration_minutes into the model's datetime/duration."""
    training = form.save(commit=False)

    date = form.cleaned_data['date']
    start_time = form.cleaned_data['start_time']
    minutes = form.cleaned_data['duration_minutes']

    naive_dt = datetime.combine(date, start_time)
    training.datetime = timezone.make_aware(naive_dt, timezone.get_current_timezone())
    training.duration = timedelta(minutes=minutes)

    training.save()
    return training


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def trainingList(request):
    if request.method == 'GET':
        return Response(TrainingSerializer(Training.objects.all(), many=True).data)

    requester, err = _requesterProfile(request)
    if err:
        return err

    form = TrainingForm(request.data)
    if not form.is_valid():
        return Response(form.errors, status=status.HTTP_400_BAD_REQUEST)

    crew = form.cleaned_data['crew']
    if not CrewMembership.objects.filter(profile=requester, crew=crew).exists():
        return Response(
            {'detail': 'Only members of the crew can create trainings for it.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    training = _saveTrainingFromForm(form)
    return Response(TrainingSerializer(training).data, status=status.HTTP_201_CREATED)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def trainingDetail(request, pk):
    try:
        training = Training.objects.get(id=pk)
    except Training.DoesNotExist:
        return Response({'detail': 'Training not found.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(TrainingSerializer(training).data)

    requester, err = _requesterProfile(request)
    if err:
        return err

    if not CrewMembership.objects.filter(profile=requester, crew=training.crew).exists():
        return Response(
            {'detail': 'Only members of this crew may modify its trainings.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == 'DELETE':
        training.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    form = TrainingForm(request.data, instance=training)
    if not form.is_valid():
        return Response(form.errors, status=status.HTTP_400_BAD_REQUEST)

    training = _saveTrainingFromForm(form)
    return Response(TrainingSerializer(training).data)


# ---------------------------------------------------------------------------
# Attendance — there is no AttendanceForm in the project, so we use the
# same get-or-create pattern as toggleAttendance in agenda/views.py.
# ---------------------------------------------------------------------------

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def attendanceList(request):
    requester, err = _requesterProfile(request)
    if err:
        return err

    if request.method == 'GET':
        crew_ids = CrewMembership.objects.filter(
            profile=requester
        ).values_list('crew_id', flat=True)
        attendances = Attendance.objects.filter(training__crew_id__in=crew_ids)
        return Response(AttendanceSerializer(attendances, many=True).data)

    training_id = request.data.get('training')
    status_value = request.data.get('status', 'pending')

    valid_statuses = {value for value, _ in Attendance.STATUS_CHOICES}
    if status_value not in valid_statuses:
        return Response({'status': ['Invalid status.']}, status=status.HTTP_400_BAD_REQUEST)

    try:
        training = Training.objects.get(id=training_id)
    except Training.DoesNotExist:
        return Response({'training': ['Training not found.']}, status=status.HTTP_400_BAD_REQUEST)

    try:
        attendance = Attendance.objects.get(training=training, athlete=requester)
        attendance.status = status_value
        attendance.save()
        created = False
    except Attendance.DoesNotExist:
        attendance = Attendance.objects.create(
            training=training, athlete=requester, status=status_value,
        )
        created = True

    return Response(
        AttendanceSerializer(attendance).data,
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def attendanceDetail(request, pk):
    try:
        attendance = Attendance.objects.get(id=pk)
    except Attendance.DoesNotExist:
        return Response({'detail': 'Attendance not found.'}, status=status.HTTP_404_NOT_FOUND)

    requester, err = _requesterProfile(request)
    if err:
        return err

    if request.method == 'GET':
        if not CrewMembership.objects.filter(
            profile=requester, crew=attendance.training.crew
        ).exists():
            return Response(
                {'detail': 'You are not a member of the relevant crew.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(AttendanceSerializer(attendance).data)

    if attendance.athlete_id != requester.id:
        return Response(
            {'detail': 'You can only modify your own attendance.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == 'DELETE':
        attendance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    status_value = request.data.get('status')
    if status_value is not None:
        valid_statuses = {value for value, _ in Attendance.STATUS_CHOICES}
        if status_value not in valid_statuses:
            return Response({'status': ['Invalid status.']}, status=status.HTTP_400_BAD_REQUEST)
        attendance.status = status_value
        attendance.save()
    return Response(AttendanceSerializer(attendance).data)


# ---------------------------------------------------------------------------
# BodyStats — strictly private to the owner. Create uses BodyStatsForm
# (matching the bodystats view), edit uses direct field assignment
# (matching editBodystats).
# ---------------------------------------------------------------------------

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def bodyStatsList(request):
    requester, err = _requesterProfile(request)
    if err:
        return err

    if request.method == 'GET':
        rows = BodyStats.objects.filter(profile=requester)
        return Response(BodyStatsSerializer(rows, many=True).data)

    form = BodyStatsForm(request.data)
    if not form.is_valid():
        return Response(form.errors, status=status.HTTP_400_BAD_REQUEST)

    today = timezone.localdate()
    stats = form.save(commit=False)
    stats.profile = requester
    stats.date = today

    try:
        existing = BodyStats.objects.get(profile=requester, date=today)
        existing.weight = stats.weight
        existing.resting_heartrate = stats.resting_heartrate
        existing.hrv = stats.hrv
        existing.body_battery = stats.body_battery
        existing.save()
        return Response(BodyStatsSerializer(existing).data)
    except BodyStats.DoesNotExist:
        stats.save()
        return Response(BodyStatsSerializer(stats).data, status=status.HTTP_201_CREATED)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def bodyStatsDetail(request, pk):
    requester, err = _requesterProfile(request)
    if err:
        return err

    try:
        row = BodyStats.objects.get(id=pk)
    except BodyStats.DoesNotExist:
        return Response({'detail': 'Body stats entry not found.'}, status=status.HTTP_404_NOT_FOUND)

    if row.profile_id != requester.id:
        return Response(
            {'detail': 'BodyStats are private to their owner.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == 'GET':
        return Response(BodyStatsSerializer(row).data)

    if request.method == 'DELETE':
        row.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # Direct field assignment — same as editBodystats in agenda/views.py.
    try:
        if 'weight' in request.data:
            row.weight = _parseDecimal(request.data.get('weight'))
        if 'resting_heartrate' in request.data:
            row.resting_heartrate = _parseInt(request.data.get('resting_heartrate'))
        if 'hrv' in request.data:
            row.hrv = _parseInt(request.data.get('hrv'))
        if 'body_battery' in request.data:
            row.body_battery = _parseInt(request.data.get('body_battery'))
        row.save()
    except (ValueError, TypeError):
        return Response({'detail': 'Invalid number entered.'}, status=status.HTTP_400_BAD_REQUEST)

    return Response(BodyStatsSerializer(row).data)
