from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.utils import timezone
from datetime import timedelta, datetime, date
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .models import Training
from users.models import Profiles, Crew, CrewMembership
from users.forms import CrewForm
from .forms import TrainingForm

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
            })

    if request.user.is_authenticated:
        try:
            profile = Profiles.objects.get(user=request.user)
            crews_for_selector = profile.crews.all()
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


def crewInfo(request, pk):
    crew = Crew.objects.get(id=pk)
    members = CrewMembership.objects.filter(crew=crew).select_related('profile')

    context = {'crew': crew, 'members': members}
    return render(request, 'agenda/crewInfo.html', context)


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