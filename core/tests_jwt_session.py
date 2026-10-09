from django.contrib.auth.models import User, Group
from django.test import TestCase
from rest_framework_simplejwt.tokens import AccessToken
class T(TestCase):
    def test_list(self):
        u=User.objects.create_user('a',password='x',is_staff=True,is_superuser=True)
        tok=str(AccessToken.for_user(u))
        r=self.client.get('/api/v1/projects/',HTTP_AUTHORIZATION='Bearer '+tok)
        self.assertEqual(r.status_code,200,r.content[:200])
        self.assertEqual(self.client.get('/api/v1/projects/').status_code,302)
