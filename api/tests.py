"""
Tests for the `api` app, organised around TMap test design techniques.

Risk areas covered:
1. JWT obtain endpoint — wrong creds must never mint a token.
2. /api/users/me/ — IsAuthenticated permission must reject anonymous calls
   and return the right user when authorised.

TMap technique reference:
- Decision table ............ Bearer header presence x validity
- Equivalence partitioning .. Credential validity (correct, wrong-pw, no-user)
"""

import json

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APITestCase

from rest_framework_simplejwt.tokens import AccessToken


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
