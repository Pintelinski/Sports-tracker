"""
Tests for the `users` app, organised around TMap test design techniques.

Risk areas covered (highest first):
1. Profile auto-creation signal — if it breaks, every signup breaks silently.
2. JWT-session middleware — auth boundary; bug here either over-locks legit users
   or leaves expired sessions accepted.
3. CrewMembership rules — uniqueness + role enumeration.

TMap technique reference:
- Process cycle test ........... User signup -> Profile created -> JWT minted
- Decision table ............... Middleware response by session-token state
- Equivalence partitioning ..... Role choices (athlete | coach | cox)
- Boundary value analysis ...... Token expiry edge (unexpired vs expired)
"""

from datetime import timedelta

from django.test import TestCase
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.urls import reverse

from rest_framework_simplejwt.tokens import RefreshToken, AccessToken

from .models import Profiles, Crew, CrewMembership
from .forms import CrewForm


# ---------------------------------------------------------------------------
# Process cycle test: User -> Profile -> JWT
# ---------------------------------------------------------------------------

class ProfileSignalTest(TestCase):
    """A Profile must be auto-created whenever a User is created (signal)."""

    def test_profile_created_on_user_create(self):
        user = User.objects.create_user(username='alice', password='pw12345!')
        profile = Profiles.objects.get(user=user)
        self.assertEqual(profile.user, user)

    def test_profile_not_recreated_on_user_save(self):
        user = User.objects.create_user(username='bob', password='pw12345!')
        user.first_name = 'Bob'
        user.save()
        self.assertEqual(Profiles.objects.filter(user=user).count(), 1)


# ---------------------------------------------------------------------------
# Decision table: JWTSessionMiddleware response by session-token state
# ---------------------------------------------------------------------------
# | request.user  | session jwt_access | expected outcome           |
# |---------------|--------------------|----------------------------|
# | anonymous     | n/a                | passes through (no logout) |
# | authenticated | missing            | logged out                 |
# | authenticated | valid              | stays logged in            |
# | authenticated | expired            | logged out                 |
#
# Tests drive the middleware end-to-end through the test client so a hit on
# any @login_required view shows the real outcome.

class JWTSessionMiddlewareTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='carol', password='pw12345!')

    def _seed_session(self, **items):
        session = self.client.session
        for k, v in items.items():
            session[k] = v
        session.save()

    def test_anonymous_request_passes_through(self):
        # Anonymous hitting a public URL is unaffected by the middleware.
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)

    def test_authenticated_with_no_token_is_logged_out(self):
        self.client.force_login(self.user)
        # No JWT in session → middleware logs the user out → @login_required redirects.
        response = self.client.get(reverse('agenda'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/login'))

    def test_authenticated_with_valid_token_stays(self):
        self.client.force_login(self.user)
        self._seed_session(
            jwt_access=str(AccessToken.for_user(self.user)),
            jwt_refresh=str(RefreshToken.for_user(self.user)),
        )
        response = self.client.get(reverse('agenda'))
        self.assertEqual(response.status_code, 200)

    def test_authenticated_with_expired_token_is_logged_out(self):
        # Boundary: build a token whose lifetime has already passed.
        token = AccessToken.for_user(self.user)
        token.set_exp(lifetime=-timedelta(seconds=1))
        self.client.force_login(self.user)
        self._seed_session(jwt_access=str(token))
        response = self.client.get(reverse('agenda'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/login'))


# ---------------------------------------------------------------------------
# Equivalence partitioning on Role + uniqueness rule on CrewMembership
# ---------------------------------------------------------------------------

class CrewMembershipRulesTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='dave', password='pw12345!')
        self.profile = Profiles.objects.get(user=self.user)
        self.crew = Crew.objects.create(name='Quad A')

    def test_each_valid_role_accepted(self):
        """Equivalence partitioning: every value in the Role partition is accepted."""
        for role, _ in CrewMembership.ROLE_CHOICES:
            with self.subTest(role=role):
                with transaction.atomic():
                    membership = CrewMembership.objects.create(
                        profile=self.profile, crew=self.crew, role=role,
                    )
                    self.assertEqual(membership.role, role)
                    membership.delete()

    def test_invalid_role_rejected_by_form(self):
        """Equivalence partitioning: a value outside the partition is rejected."""
        form = CrewForm(data={'name': 'Quad B', 'role': 'captain'})
        self.assertFalse(form.is_valid())
        self.assertIn('role', form.errors)

    def test_duplicate_membership_violates_unique_together(self):
        """Decision table: same (profile, crew) twice raises IntegrityError."""
        CrewMembership.objects.create(profile=self.profile, crew=self.crew, role='athlete')
        with self.assertRaises(IntegrityError):
            CrewMembership.objects.create(profile=self.profile, crew=self.crew, role='coach')


# ---------------------------------------------------------------------------
# Use case test: full login flow stores a valid JWT in the session
# ---------------------------------------------------------------------------

class LoginUseCaseTest(TestCase):

    def test_login_stores_jwt_and_redirects(self):
        User.objects.create_user(username='eve', password='pw12345!')
        response = self.client.post(reverse('login'),
                                    {'username': 'eve', 'password': 'pw12345!'},
                                    follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn('jwt_refresh', self.client.session)
        self.assertIn('jwt_access', self.client.session)
        # Token in session must be valid (not just present)
        RefreshToken(self.client.session['jwt_refresh'])

    def test_login_with_wrong_password_does_not_set_token(self):
        User.objects.create_user(username='frank', password='pw12345!')
        self.client.post(reverse('login'),
                         {'username': 'frank', 'password': 'WRONG'})
        self.assertNotIn('jwt_refresh', self.client.session)
