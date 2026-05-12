from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse, Http404
from django.utils import timezone
from datetime import timedelta, datetime, date
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse

from django.views.decorators.http import require_POST
import uuid

from icalendar import Calendar, Event

from .models import Training, Attendance
from users.models import Profiles, Crew, CrewMembership
from users.forms import CrewForm
from .forms import TrainingForm

ATTENDANCE_CYCLE = {'pending': 'present', 'present': 'absent', 'absent': 'pending'}


def ensureCalendarToken(profile):
    if profile.calendar_token is None:
        profile.calendar_token = uuid.uuid4()
        profile.save(update_fields=['calendar_token'])
    return profile.calendar_token


def buildIcs(trainings, calendar_name):
    cal = Calendar()
    cal.add('prodid', '-//Sportstracker//Crew agenda//EN')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', calendar_name)

    for t in trainings:
        event = Event()
        event.add('uid', f'training-{t.id}@sportstracker')
        event.add('summary', f'{t.title} ({t.crew.name})')
        event.add('dtstart', t.datetime)
        event.add('dtend', t.datetime + t.duration)
        event.add('dtstamp', timezone.now())
        if t.description:
            event.add('description', t.description)
        event.add('categories', [t.get_intensity_display()])
        cal.add_component(event)

    return cal.to_ical()

@login_required(login_url='login')
def bodystats(request):
    return render(request, 'agenda/bodystats.html')


@login_required(login_url='login')
def agenda(request):
    today = timezone.localdate()
    start_str = request.GET.get('start')
    try:
        if start_str:
            week_start = datetime.fromisoformat(start_str).date()
        else:
            week_start = today - timedelta(days=today.weekday())
    except Exception:
        week_start = today - timedelta(days=today.weekday())

    week_days = [week_start + timedelta(days=i) for i in range(7)]
    week_end = week_start + timedelta(days=6)

    hours = list(range(6, 24))

    crew_param = request.GET.get('crew', 'personal')
    trainings_qs = Training.objects.filter(datetime__date__gte=week_start, datetime__date__lte=week_end).select_related('crew')

    if crew_param and crew_param != 'all':
        if crew_param == 'personal' and request.user.is_authenticated:
            try:
                profile = Profiles.objects.get(user=request.user)
                user_crews = profile.crews.all()
                trainings_qs = trainings_qs.filter(crew__in=user_crews)
            except Profiles.DoesNotExist:
                trainings_qs = trainings_qs.none()
        else:
            try:
                profile = Profiles.objects.get(user=request.user)
                crew_obj = profile.crews.get(id=crew_param)
                trainings_qs = trainings_qs.filter(crew=crew_obj)
            except (Profiles.DoesNotExist, Crew.DoesNotExist):
                trainings_qs = trainings_qs.none()

    my_attendance_by_training = {}
    if request.user.is_authenticated:
        try:
            my_profile = Profiles.objects.get(user=request.user)
            my_attendance_by_training = {
                a.training_id: a.status
                for a in Attendance.objects.filter(
                    athlete=my_profile, training__in=trainings_qs
                )
            }
        except Profiles.DoesNotExist:
            pass

    trainings_by_date = {d.isoformat(): [] for d in week_days}
    for t in trainings_qs:
        local_dt = timezone.localtime(t.datetime)
        t_date_iso = local_dt.date().isoformat()
        if t_date_iso in trainings_by_date:
            trainings_by_date[t_date_iso].append({
                'id': t.id,
                'title': t.title,
                'start': local_dt,
                'duration': t.duration,
                'crew': t.crew,
                'intensity': t.intensity,
                'my_status': my_attendance_by_training.get(t.id, 'pending'),
            })

    feed_url = None
    if request.user.is_authenticated:
        try:
            profile = Profiles.objects.get(user=request.user)
            crews_for_selector = profile.crews.all()
            token = ensureCalendarToken(profile)
            path = reverse('personal-calendar-feed', args=[token])
            feed_url = request.build_absolute_uri(path)
        except Profiles.DoesNotExist:
            crews_for_selector = Crew.objects.none()
    else:
        crews_for_selector = Crew.objects.none()

    week_map = []
    for d in week_days:
        key = d.isoformat()
        week_map.append({
            'date': d,
            'trainings': trainings_by_date.get(key, [])
        })

    week_start_iso = week_start.isoformat()
    week_prev_iso = (week_start - timedelta(days=7)).isoformat()
    week_next_iso = (week_start + timedelta(days=7)).isoformat()

    context = {
        'week_days': week_days,
        'hours': hours,
        'trainings_by_date': trainings_by_date,
        'week_map': week_map,
        'week_start': week_start,
        'week_start_iso': week_start_iso,
        'week_prev_iso': week_prev_iso,
        'week_next_iso': week_next_iso,
        'crews': crews_for_selector,
        'selected_crew': crew_param,
        'feed_url': feed_url,
    }

    return render(request, 'agenda/agenda.html', context)


@login_required(login_url='login')
def crewsPage(request):
    crews = Crew.objects.all()

    context = {'crews': crews}
    return render(request, 'agenda/crews.html', context)


@login_required(login_url='login')
def createCrew(request):
    profile = request.user.profiles
    form = CrewForm()

    if request.method == 'POST':
        form = CrewForm(request.POST)
        if form.is_valid():
            crew = form.save(commit=False)
            crew._pending_member_profile = profile
            crew._pending_member_role = form.cleaned_data['role']
            crew.save()

            messages.success(request, 'Crew was created succesfully')

            return redirect('crews')


    context = {'form': form}
    return render(request, "agenda/crew_form.html", context)


def crewInfo(request, pk):
    crew = Crew.objects.get(id=pk)
    members = CrewMembership.objects.filter(crew=crew).select_related('profile')

    feed_url = None
    if request.user.is_authenticated:
        try:
            profile = Profiles.objects.get(user=request.user)
            token = ensureCalendarToken(profile)
            path = reverse('crew-calendar-feed', args=[crew.id, token])
            feed_url = request.build_absolute_uri(path)
        except Profiles.DoesNotExist:
            pass

    context = {'crew': crew, 'members': members, 'feed_url': feed_url}
    return render(request, 'agenda/crewInfo.html', context)


def crewCalendarFeed(request, pk, token):
    try:
        profile = Profiles.objects.get(calendar_token=token)
    except Profiles.DoesNotExist:
        raise Http404('Invalid calendar token')

    try:
        crew = profile.crews.get(id=pk)
    except Crew.DoesNotExist:
        raise Http404('Not a member of this crew')

    trainings = Training.objects.filter(crew=crew).select_related('crew')
    ics = buildIcs(trainings, calendar_name=f'{crew.name} trainings')

    response = HttpResponse(ics, content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = f'inline; filename="crew-{crew.id}.ics"'
    return response


def personalCalendarFeed(request, token):
    try:
        profile = Profiles.objects.get(calendar_token=token)
    except Profiles.DoesNotExist:
        raise Http404('Invalid calendar token')

    user_crews = profile.crews.all()
    trainings = Training.objects.filter(crew__in=user_crews).select_related('crew')
    ics = buildIcs(trainings, calendar_name='My Sportstracker agenda')

    response = HttpResponse(ics, content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = f'inline; filename="my-agenda.ics"'
    return response


@login_required(login_url='login')
def addMemberToCrew(request, pk):
    crew = Crew.objects.get(id=pk)
    members = CrewMembership.objects.filter(crew=crew).select_related('profile')

    if request.method == 'POST':
        selected_ids = request.POST.getlist('profile_ids')
        valid_roles = {value for value, _ in CrewMembership.ROLE_CHOICES}

        added = 0
        for pid in selected_ids:
            try:
                profile = Profiles.objects.get(id=pid)
            except Profiles.DoesNotExist:
                continue

            role = request.POST.get(f'role_{pid}', 'athlete')
            if role not in valid_roles:
                role = 'athlete'

            crew._pending_member_profile = profile
            crew._pending_member_role = role
            crew.save()
            added += 1

        if added:
            messages.success(request, f'{added} member(s) added to {crew.name}')
        else:
            messages.info(request, 'No new members were added')

        return redirect('crew-info', crew.id)

    existing_profile_ids = members.values_list('profile_id', flat=True)
    profiles = Profiles.objects.exclude(id__in=existing_profile_ids)

    roles = CrewMembership.ROLE_CHOICES

    context = {'crew': crew, 'profiles': profiles, 'members': members, 'roles': roles}
    return render(request, 'agenda/add_member.html', context)

@login_required(login_url='login')
def createTraining(request):
    form = TrainingForm()

    if request.method == 'POST':
        form = TrainingForm(request.POST)
        if form.is_valid():
            training = form.save(commit=False)

            date = form.cleaned_data['date']
            start_time = form.cleaned_data['start_time']
            minutes = form.cleaned_data['duration_minutes']

            naive_dt = datetime.combine(date, start_time)
            training.datetime = timezone.make_aware(naive_dt, timezone.get_current_timezone())
            training.duration = timedelta(minutes=minutes)

            training.save()

            messages.success(request, 'Training was created successfully')

            return redirect('agenda')

    context = {'form': form}
    return render(request, 'agenda/add_training.html', context)

@login_required(login_url='login')
def trainingInfo(request, pk):
    training = Training.objects.select_related('crew').get(id=pk)

    memberships = CrewMembership.objects.filter(crew=training.crew).select_related('profile')
    attendance_by_profile = {
        a.athlete_id: a.status
        for a in Attendance.objects.filter(training=training)
    }

    crew_attendance = [
        {
            'profile': m.profile,
            'role': m.get_role_display(),
            'status': attendance_by_profile.get(m.profile_id, 'pending'),
        }
        for m in memberships
    ]

    my_status = 'pending'
    try:
        my_profile = Profiles.objects.get(user=request.user)
        my_status = attendance_by_profile.get(my_profile.id, 'pending')
    except Profiles.DoesNotExist:
        my_profile = None

    context = {
        'training': training,
        'crew_attendance': crew_attendance,
        'my_status': my_status,
        'my_profile': my_profile,
    }
    return render(request, 'agenda/training_info.html', context)


@login_required(login_url='login')
@require_POST
def toggleAttendance(request, pk):
    training = Training.objects.get(id=pk)
    try:
        profile = Profiles.objects.get(user=request.user)
    except Profiles.DoesNotExist:
        messages.error(request, 'No profile found for your account.')
        return redirect('agenda')

    try:
        attendance = Attendance.objects.get(training=training, athlete=profile)
        attendance.status = ATTENDANCE_CYCLE.get(attendance.status, 'pending')
        attendance.save()
    except Attendance.DoesNotExist:
        attendance = Attendance.objects.create(
            training=training,
            athlete=profile,
            status='present',
        )

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': attendance.status})

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER')
    if next_url:
        return redirect(next_url)
    return redirect('agenda')