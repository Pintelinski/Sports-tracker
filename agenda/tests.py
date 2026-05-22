"""
Tests for the `agenda` app, organised around TMap test design techniques.

Risk areas covered (highest first):
1. Privacy boundary on BodyStats — must never let user A read or edit user B.
2. Attendance state machine — pending -> present -> absent -> pending.
3. Authorisation on adding crew members — non-members must be refused.
4. ICS feed token gate — wrong token must 404; right token must list events.
5. Reminder banner trigger on the agenda page (today's BodyStats present).

TMap technique reference:
- Decision table ............... Attendance cycle transitions
- Boundary value analysis ...... BodyStats partial entry / numeric edges
- Equivalence partitioning ..... Intensity choices on Training
- Use case test ................ Add-member authorisation flow
- Real-life test ............... Subscribe-to-feed flow with token
- Process cycle test ........... Logging today's BodyStats removes the banner
"""

from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.urls import reverse
from django.utils import timezone

from rest_framework_simplejwt.tokens import RefreshToken

from .models import Training, Attendance, BodyStats
from .forms import TrainingForm
from users.models import Profiles, Crew, CrewMembership


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(username, password='pw12345!'):
    user = User.objects.create_user(username=username, password=password)
    return user, Profiles.objects.get(user=user)


def make_crew(name, members):
    crew = Crew.objects.create(name=name)
    for profile, role in members:
        CrewMembership.objects.create(profile=profile, crew=crew, role=role)
    return crew


def make_training(crew, when=None, duration_minutes=60, **overrides):
    when = when or timezone.now() + timedelta(days=1)
    return Training.objects.create(
        crew=crew,
        title=overrides.get('title', 'Morning row'),
        datetime=when,
        duration=timedelta(minutes=duration_minutes),
        intensity=overrides.get('intensity', 'T2'),
        description=overrides.get('description', ''),
    )


class JwtClientMixin:
    """Logs in via the test client AND seeds a valid JWT in the session,
    so JWTSessionMiddleware doesn't immediately log the test user out."""

    def login_with_jwt(self, username, password='pw12345!'):
        self.client.login(username=username, password=password)
        user = User.objects.get(username=username)
        refresh = RefreshToken.for_user(user)
        session = self.client.session
        session['jwt_refresh'] = str(refresh)
        session['jwt_access'] = str(refresh.access_token)
        session.save()


# ---------------------------------------------------------------------------
# Decision table: attendance cycle
# ---------------------------------------------------------------------------
# | current state | click outcome |
# |---------------|---------------|
# | (no record)   | present       |
# | pending       | present       |
# | present       | absent        |
# | absent        | pending       |

class AttendanceCycleTest(JwtClientMixin, TestCase):

    def setUp(self):
        self.user, self.profile = make_user('alice')
        self.crew = make_crew('Quad A', [(self.profile, 'athlete')])
        self.training = make_training(self.crew)
        self.login_with_jwt('alice')

    def _toggle(self):
        return self.client.post(reverse('toggle-attendance', args=[self.training.id]))

    def _current_status(self):
        try:
            return Attendance.objects.get(training=self.training, athlete=self.profile).status
        except Attendance.DoesNotExist:
            return None

    def test_first_click_creates_present(self):
        self._toggle()
        self.assertEqual(self._current_status(), 'present')

    def test_pending_to_present(self):
        Attendance.objects.create(training=self.training, athlete=self.profile, status='pending')
        self._toggle()
        self.assertEqual(self._current_status(), 'present')

    def test_present_to_absent(self):
        Attendance.objects.create(training=self.training, athlete=self.profile, status='present')
        self._toggle()
        self.assertEqual(self._current_status(), 'absent')

    def test_absent_to_pending(self):
        Attendance.objects.create(training=self.training, athlete=self.profile, status='absent')
        self._toggle()
        self.assertEqual(self._current_status(), 'pending')


# ---------------------------------------------------------------------------
# Boundary value analysis + uniqueness on BodyStats
# ---------------------------------------------------------------------------

class BodyStatsModelTest(TestCase):

    def setUp(self):
        _, self.profile = make_user('grace')

    def test_partial_entry_with_only_weight_allowed(self):
        """All metric fields are nullable — user can record weight only."""
        stats = BodyStats.objects.create(
            profile=self.profile, date=date.today(), weight=Decimal('72.5'),
        )
        self.assertIsNone(stats.resting_heartrate)
        self.assertIsNone(stats.hrv)
        self.assertIsNone(stats.body_battery)

    def test_body_battery_lower_boundary_zero(self):
        BodyStats.objects.create(profile=self.profile, date=date.today(), body_battery=0)
        self.assertEqual(BodyStats.objects.get(profile=self.profile).body_battery, 0)

    def test_body_battery_upper_boundary_hundred(self):
        BodyStats.objects.create(profile=self.profile, date=date.today(), body_battery=100)
        self.assertEqual(BodyStats.objects.get(profile=self.profile).body_battery, 100)

    def test_unique_per_profile_per_date(self):
        BodyStats.objects.create(profile=self.profile, date=date.today(), weight=Decimal('70.0'))
        with self.assertRaises(IntegrityError):
            BodyStats.objects.create(profile=self.profile, date=date.today(), weight=Decimal('71.0'))


# ---------------------------------------------------------------------------
# Privacy boundary: user A cannot read/edit user B's BodyStats
# ---------------------------------------------------------------------------

class BodyStatsPrivacyTest(JwtClientMixin, TestCase):

    def setUp(self):
        _, self.alice = make_user('alice')
        self.bob_user, self.bob = make_user('bob')
        self.bob_stats = BodyStats.objects.create(
            profile=self.bob, date=date.today(), weight=Decimal('80.0'),
        )

    def test_user_does_not_see_other_users_history(self):
        self.login_with_jwt('alice')
        response = self.client.get(reverse('bodystats'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '80.0')

    def test_user_cannot_edit_other_users_row(self):
        self.login_with_jwt('alice')
        url = reverse('edit-bodystats', args=[self.bob_stats.id])
        self.client.post(url, {'weight': '99.99'})
        self.bob_stats.refresh_from_db()
        # Bob's row must be unchanged.
        self.assertEqual(self.bob_stats.weight, Decimal('80.0'))


# ---------------------------------------------------------------------------
# Equivalence partitioning: Training intensity choices
# ---------------------------------------------------------------------------

class TrainingIntensityPartitionTest(TestCase):

    def setUp(self):
        _, self.profile = make_user('helen')
        self.crew = make_crew('Eight', [(self.profile, 'athlete')])

    def _form(self, intensity):
        return TrainingForm(data={
            'title': 'X',
            'description': '',
            'intensity': intensity,
            'crew': self.crew.id,
            'date': date.today().isoformat(),
            'start_time': '08:00',
            'duration_minutes': 60,
        })

    def test_each_valid_intensity_accepted(self):
        for code, _ in Training.INTENSITY_CHOICES:
            with self.subTest(intensity=code):
                self.assertTrue(self._form(code).is_valid())

    def test_invalid_intensity_rejected(self):
        self.assertFalse(self._form('T6').is_valid())


# ---------------------------------------------------------------------------
# Use case test: only members can open the add-member page
# ---------------------------------------------------------------------------

class AddMemberAuthorisationTest(JwtClientMixin, TestCase):

    def setUp(self):
        _, self.member = make_user('alice')
        _, self.outsider = make_user('mallory')
        self.crew = make_crew('Quad A', [(self.member, 'athlete')])

    def test_member_can_open_add_member_page(self):
        self.login_with_jwt('alice')
        response = self.client.get(reverse('add-member-to-crew', args=[self.crew.id]))
        self.assertEqual(response.status_code, 200)

    def test_outsider_is_redirected_back_to_crew_info(self):
        self.login_with_jwt('mallory')
        response = self.client.get(reverse('add-member-to-crew', args=[self.crew.id]))
        self.assertRedirects(response, reverse('crew-info', args=[self.crew.id]))

    def test_outsider_cannot_add_via_post(self):
        self.login_with_jwt('mallory')
        before = CrewMembership.objects.filter(crew=self.crew).count()
        self.client.post(
            reverse('add-member-to-crew', args=[self.crew.id]),
            {'profile_ids': [str(self.outsider.id)], f'role_{self.outsider.id}': 'athlete'},
        )
        after = CrewMembership.objects.filter(crew=self.crew).count()
        self.assertEqual(before, after)


# ---------------------------------------------------------------------------
# Real-life test: ICS feed authentication via the URL token
# ---------------------------------------------------------------------------

class IcsFeedTest(TestCase):

    def setUp(self):
        _, self.profile = make_user('alice')
        self.crew = make_crew('Quad A', [(self.profile, 'athlete')])
        self.training = make_training(self.crew, when=timezone.now() + timedelta(hours=2))
        # Mint the token directly — tested separately by the view-level reminder test.
        from agenda.views import ensureCalendarToken
        self.token = ensureCalendarToken(self.profile)

    def test_personal_feed_returns_ics_with_event(self):
        url = reverse('personal-calendar-feed', args=[self.token])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'].split(';')[0], 'text/calendar')
        body = response.content.decode()
        self.assertIn('BEGIN:VCALENDAR', body)
        self.assertIn('BEGIN:VEVENT', body)
        self.assertIn(f'training-{self.training.id}@sportstracker', body)

    def test_invalid_token_returns_404(self):
        bogus = '00000000-0000-0000-0000-000000000000'
        url = reverse('personal-calendar-feed', args=[bogus])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_crew_feed_rejects_token_for_crew_user_is_not_in(self):
        other_crew = Crew.objects.create(name='Strangers')
        url = reverse('crew-calendar-feed', args=[other_crew.id, self.token])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# Process cycle test: logging today's BodyStats clears the agenda reminder
# ---------------------------------------------------------------------------

class AgendaReminderTest(JwtClientMixin, TestCase):

    def setUp(self):
        self.user, self.profile = make_user('alice')
        self.login_with_jwt('alice')

    def test_reminder_shown_when_today_not_logged(self):
        response = self.client.get(reverse('agenda'))
        self.assertTrue(response.context['needs_bodystats_today'])

    def test_reminder_hidden_after_logging_today(self):
        BodyStats.objects.create(profile=self.profile, date=timezone.localdate(), weight=Decimal('70.0'))
        response = self.client.get(reverse('agenda'))
        self.assertFalse(response.context['needs_bodystats_today'])
