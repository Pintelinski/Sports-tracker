"""
Tests for the `api` app, organised around TMap test design techniques.

Risk areas covered:
1. JWT obtain endpoint — wrong creds must never mint a token.
2. /api/users/me/ — IsAuthenticated permission must reject anonymous calls
   and return the right user when authorised.
3. CRUD endpoints — must respect the same privacy/authorisation rules as the UI:
   BodyStats are owner-only; only crew members can mutate crews/trainings/memberships;
   Attendance can only be set by the athlete it belongs to.

TMap technique reference:
- Decision table ............ Bearer header presence x validity
- Equivalence partitioning .. Credential validity (correct, wrong-pw, no-user)
- Use case test ............. Owner vs other-user CRUD on private resources
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from rest_framework_simplejwt.tokens import AccessToken

from agenda.models import Training, BodyStats
from users.models import Profiles, Crew, CrewMembership


class JwtTokenObtainTest(APITestCase):
    """Equivalence partitioning on credential validity."""

    def setUp(self):
        User.objects.create_user(username='alice', password='pw12345!')

    def test_correct_credentials_returns_pair(self):
        response = self.client.post(reverse('token_obtain_pair'),
                                    {'username': 'alice', 'password': 'pw12345!'},
                                    format='json')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn('access', body)
        self.assertIn('refresh', body)

    def test_wrong_password_returns_401(self):
        response = self.client.post(reverse('token_obtain_pair'),
                                    {'username': 'alice', 'password': 'WRONG'},
                                    format='json')
        self.assertEqual(response.status_code, 401)

    def test_unknown_user_returns_401(self):
        response = self.client.post(reverse('token_obtain_pair'),
                                    {'username': 'noone', 'password': 'pw12345!'},
                                    format='json')
        self.assertEqual(response.status_code, 401)


class CurrentUserApiTest(APITestCase):
    """Decision table: Bearer header presence x validity on /api/users/me/."""

    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='pw12345!')
        self.url = reverse('current-user')

    def test_anonymous_returns_401(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_invalid_bearer_returns_401(self):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer not-a-real-token')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_valid_bearer_returns_user(self):
        access = str(AccessToken.for_user(self.user))
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['username'], 'alice')


class TokenRefreshTest(APITestCase):
    """A valid refresh token mints a new access token."""

    def setUp(self):
        User.objects.create_user(username='alice', password='pw12345!')
        obtain = self.client.post(reverse('token_obtain_pair'),
                                  {'username': 'alice', 'password': 'pw12345!'},
                                  format='json')
        self.refresh = obtain.json()['refresh']

    def test_refresh_returns_new_access(self):
        response = self.client.post(reverse('token_refresh'),
                                    {'refresh': self.refresh},
                                    format='json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.json())

    def test_garbage_refresh_returns_401(self):
        response = self.client.post(reverse('token_refresh'),
                                    {'refresh': 'not-a-jwt'},
                                    format='json')
        self.assertEqual(response.status_code, 401)


# ---------------------------------------------------------------------------
# CRUD endpoints — authorisation must mirror the UI rules
# ---------------------------------------------------------------------------

class ApiAuthMixin:
    """Authenticate the test client with a Bearer JWT for the given user."""

    def auth_as(self, user):
        access = str(AccessToken.for_user(user))
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')


class BodyStatsApiTest(ApiAuthMixin, APITestCase):
    """BodyStats are private — owner sees their rows, never anyone else's."""

    def setUp(self):
        self.alice_user = User.objects.create_user(username='alice', password='pw12345!')
        self.bob_user = User.objects.create_user(username='bob', password='pw12345!')
        self.alice = Profiles.objects.get(user=self.alice_user)
        self.bob = Profiles.objects.get(user=self.bob_user)
        self.bob_row = BodyStats.objects.create(
            profile=self.bob, date=date.today(), weight=Decimal('80.0'),
        )

    def test_anonymous_is_rejected(self):
        response = self.client.get(reverse('api-bodystats-list'))
        self.assertEqual(response.status_code, 401)

    def test_owner_sees_only_own_rows(self):
        BodyStats.objects.create(profile=self.alice, date=date.today(), weight=Decimal('70.0'))
        self.auth_as(self.alice_user)
        response = self.client.get(reverse('api-bodystats-list'))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]['weight'], '70.00')

    def test_other_user_cannot_read_row(self):
        self.auth_as(self.alice_user)
        response = self.client.get(reverse('api-bodystats-detail', args=[self.bob_row.id]))
        self.assertEqual(response.status_code, 403)

    def test_other_user_cannot_edit_row(self):
        self.auth_as(self.alice_user)
        response = self.client.patch(
            reverse('api-bodystats-detail', args=[self.bob_row.id]),
            {'weight': '99.99'}, format='json',
        )
        self.assertEqual(response.status_code, 403)
        self.bob_row.refresh_from_db()
        self.assertEqual(self.bob_row.weight, Decimal('80.0'))

    def test_post_forces_profile_to_requester(self):
        self.auth_as(self.alice_user)
        # Even if the client lies and says profile=Bob, the row must land on Alice.
        response = self.client.post(
            reverse('api-bodystats-list'),
            {'date': str(date.today()), 'weight': '65.5', 'profile': str(self.bob.id)},
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        new_row = BodyStats.objects.get(weight=Decimal('65.5'))
        self.assertEqual(new_row.profile_id, self.alice.id)


class TrainingApiTest(ApiAuthMixin, APITestCase):
    """Trainings: only crew members may create/modify."""

    def setUp(self):
        self.member_user = User.objects.create_user(username='alice', password='pw12345!')
        self.outsider_user = User.objects.create_user(username='mallory', password='pw12345!')
        self.member = Profiles.objects.get(user=self.member_user)
        self.crew = Crew.objects.create(name='Quad A')
        CrewMembership.objects.create(profile=self.member, crew=self.crew, role='athlete')

    def _payload(self):
        tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
        return {
            'title': 'Morning row',
            'date': tomorrow,
            'start_time': '08:00',
            'duration_minutes': 60,
            'intensity': 'T2',
            'description': '',
            'crew': str(self.crew.id),
        }

    def test_member_can_create_training(self):
        self.auth_as(self.member_user)
        response = self.client.post(reverse('api-training-list'), self._payload(), format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Training.objects.count(), 1)

    def test_outsider_cannot_create_training(self):
        self.auth_as(self.outsider_user)
        response = self.client.post(reverse('api-training-list'), self._payload(), format='json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Training.objects.count(), 0)


class MembershipApiTest(ApiAuthMixin, APITestCase):
    """Only existing members may add others to a crew (matches the UI rule)."""

    def setUp(self):
        self.member_user = User.objects.create_user(username='alice', password='pw12345!')
        self.outsider_user = User.objects.create_user(username='mallory', password='pw12345!')
        self.member = Profiles.objects.get(user=self.member_user)
        self.outsider = Profiles.objects.get(user=self.outsider_user)
        self.crew = Crew.objects.create(name='Quad A')
        CrewMembership.objects.create(profile=self.member, crew=self.crew, role='athlete')

    def test_outsider_cannot_add_themselves(self):
        self.auth_as(self.outsider_user)
        response = self.client.post(
            reverse('api-membership-list'),
            {'profile': str(self.outsider.id), 'crew': str(self.crew.id), 'role': 'athlete'},
            format='json',
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(CrewMembership.objects.filter(crew=self.crew).count(), 1)

    def test_member_can_add_someone(self):
        self.auth_as(self.member_user)
        response = self.client.post(
            reverse('api-membership-list'),
            {'profile': str(self.outsider.id), 'crew': str(self.crew.id), 'role': 'cox'},
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(CrewMembership.objects.filter(crew=self.crew).count(), 2)
