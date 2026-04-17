from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.utils import timezone
from datetime import timedelta, datetime, date
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .models import Training
from users.models import Profiles, Crew, CrewMembership
from users.forms import CrewForm

@login_required(login_url='login')
def bodystats(request):
    return render(request, 'agenda/bodystats.html')


@login_required(login_url='login')
def agenda(request):
    """Render a weekly agenda view with hour slots and trainings.

    Query params:
    - start: YYYY-MM-DD date for Monday of the week to show (optional)
    - crew: 'all', 'personal', or a Crew id to filter trainings
    """
    # determine week start (Monday)
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

    # hours to display (adjustable)
    hours = list(range(0, 24))

    # crew filtering
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
            # try to filter by specific crew id
            try:
                crew_obj = Crew.objects.get(id=crew_param)
                trainings_qs = trainings_qs.filter(crew=crew_obj)
            except Exception:
                # invalid crew param -> no trainings
                trainings_qs = trainings_qs.none()

    # organize trainings by date (keys are ISO strings for template indexing)
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
            })

    # list of crews to show in the selector: for logged-in users show their crews
    if request.user.is_authenticated:
        try:
            profile = Profiles.objects.get(user=request.user)
            crews_for_selector = profile.crews.all()
        except Profiles.DoesNotExist:
            crews_for_selector = Crew.objects.none()
    else:
        # anonymous users: show no personal crews (could be adjusted to show all)
        crews_for_selector = Crew.objects.none()

    # prepare a list of dicts pairing each day with its trainings for easy template iteration
    week_map = []
    for d in week_days:
        key = d.isoformat()
        week_map.append({
            'date': d,
            'trainings': trainings_by_date.get(key, [])
        })

    # ISO strings for use in URLs/templates
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
            crew = form.save()
            CrewMembership.objects.create(
                profile=profile,
                crew=crew,
                role=form.cleaned_data['role'],
            )
            return redirect('crews')


    context = {'form': form}
    return render(request, "agenda/crew_form.html", context)


def crewInfo(request, pk):
    crew = Crew.objects.get(id=pk)
    members = CrewMembership.objects.filter(crew=crew).select_related('profile')

    can_add_members = False
    if request.user.is_authenticated:
        try:
            current_profile = request.user.profiles
            can_add_members = members.filter(profile=current_profile).exists()
        except Profiles.DoesNotExist:
            can_add_members = False

    context = {'crew': crew, 'members': members, 'can_add_members': can_add_members}
    return render(request, 'agenda/crewInfo.html', context)


@login_required(login_url='login')
def addMemberToCrew(request, pk):
    crew = Crew.objects.get(id=pk)
    members = CrewMembership.objects.filter(crew=crew).select_related('profile')

    try:
        current_profile = request.user.profiles
    except Profiles.DoesNotExist:
        messages.error(request, 'No profile found for this account.')
        return redirect('crew-info', pk=pk)

    if not members.filter(profile=current_profile).exists():
        messages.error(request, 'Only crew members can add other members.')
        return redirect('crew-info', pk=pk)

    member_profile_ids = members.values_list('profile_id', flat=True)
    profiles = Profiles.objects.exclude(id__in=member_profile_ids)
    role_choices = CrewMembership.ROLE_CHOICES
    allowed_roles = {key for key, _ in role_choices}

    if request.method == 'POST':
        selected_profile_ids = request.POST.getlist('profile_ids')

        if not selected_profile_ids:
            messages.warning(request, 'Select at least one profile to add.')
            return redirect('add-member-to-crew', pk=pk)

        added_count = 0
        for profile in profiles.filter(id__in=selected_profile_ids):
            selected_role = request.POST.get(f'role_{profile.id}', 'athlete')
            if selected_role not in allowed_roles:
                selected_role = 'athlete'

            membership, created = CrewMembership.objects.get_or_create(
                crew=crew,
                profile=profile,
                defaults={'role': selected_role},
            )

            if not created and membership.role != selected_role:
                membership.role = selected_role
                membership.save(update_fields=['role'])

            if created:
                added_count += 1

        if added_count:
            messages.success(request, f'Added {added_count} member(s) to {crew.name}.')
        else:
            messages.info(request, 'No new members were added.')

        return redirect('crew-info', pk=pk)


    context = {'crew': crew, 'profiles': profiles, 'members': members, 'role_choices': role_choices}
    return render(request, 'agenda/add_member.html', context)