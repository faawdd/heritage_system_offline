import io
import logging
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import UserProfile
from core.services.account_security import SECURITY_QUESTION_BANK, hash_security_questions
from desktop_backend import _ensure_initial_admin


QUESTION_SET = [
    {'question_id': 'childhood_city', 'answer': '青城'},
    {'question_id': 'first_school', 'answer': '晨光小学'},
    {'question_id': 'first_pet', 'answer': '小白'},
]


class AccountSecurityApiTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_superuser(
            username='security-admin',
            email='security-admin@example.test',
            password='Original!Pass2026',
        )
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(self.admin)
        self.public_client = APIClient()

    def test_security_question_bank_contains_twelve_questions(self):
        response = self.public_client.get('/api/v1/system/security-questions/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['questions']), 12)
        self.assertEqual(len(SECURITY_QUESTION_BANK), 12)

    def test_legacy_user_must_setup_questions_before_receiving_login_tokens(self):
        legacy_user = get_user_model().objects.create_user(
            username='legacy-user',
            password='Legacy!Pass2026',
        )
        response = self.public_client.post('/api/v1/system/login/', {
            'username': legacy_user.username,
            'password': 'Legacy!Pass2026',
        }, format='json')
        self.assertEqual(response.status_code, 428)
        self.assertEqual(response.data['code'], 'SECURITY_QUESTIONS_REQUIRED')

        response = self.public_client.post('/api/v1/system/login/', {
            'username': legacy_user.username,
            'password': 'Legacy!Pass2026',
            'security_questions': QUESTION_SET,
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['data']['access_token'])
        self.assertEqual(len(UserProfile.objects.get(user=legacy_user).security_questions), 3)

    def test_existing_admin_without_security_questions_does_not_abort_backend_bootstrap(self):
        profile = UserProfile.objects.get(user=self.admin)
        profile.security_questions = []
        profile.save(update_fields=['security_questions'])

        with patch('desktop_backend.sys.stdin', io.StringIO('[]\n')):
            _ensure_initial_admin(logging.getLogger('account-security-test'))

        profile.refresh_from_db()
        self.assertEqual(profile.security_questions, [])

    def test_initial_admin_can_bootstrap_without_security_questions(self):
        self.admin.delete()

        with patch('desktop_backend.sys.stdin', io.StringIO('[]\n')):
            _ensure_initial_admin(logging.getLogger('account-security-test'))

        admin = get_user_model().objects.get(username='admin')
        profile = UserProfile.objects.get(user=admin)
        self.assertTrue(admin.is_superuser)
        self.assertFalse(profile.has_changed_password)
        self.assertEqual(profile.security_questions, [])

    def test_user_creation_requires_three_security_questions_and_hashes_answers(self):
        response = self.admin_client.post('/api/v1/system/users/', {
            'username': 'new-security-user',
            'password': 'Initial!Pass2026',
        }, format='json')
        self.assertEqual(response.status_code, 400)

        response = self.admin_client.post('/api/v1/system/users/', {
            'username': 'new-security-user',
            'password': 'Initial!Pass2026',
            'security_questions': QUESTION_SET,
        }, format='json')
        self.assertEqual(response.status_code, 201)

        profile = UserProfile.objects.get(user__username='new-security-user')
        self.assertEqual(len(profile.security_questions), 3)
        self.assertNotIn('青城', str(profile.security_questions))
        self.assertTrue(profile.security_questions[0]['answer_hash'].startswith('pbkdf2_'))

    def test_password_change_requires_and_saves_security_questions(self):
        response = self.admin_client.post('/api/v1/system/profile/change-password/', {
            'old_password': 'Original!Pass2026',
            'new_password': 'Updated!Pass2026',
        }, format='json')
        self.assertEqual(response.status_code, 400)

        response = self.admin_client.post('/api/v1/system/profile/change-password/', {
            'old_password': 'Original!Pass2026',
            'new_password': 'Updated!Pass2026',
            'security_questions': QUESTION_SET,
        }, format='json')
        self.assertEqual(response.status_code, 200)
        profile = UserProfile.objects.get(user=self.admin)
        self.assertEqual(len(profile.security_questions), 3)

    def test_admin_password_reset_requires_replacement_security_questions(self):
        target = get_user_model().objects.create_user(username='managed-user', password='Previous!Pass2026')
        UserProfile.objects.filter(user=target).update(security_questions=hash_security_questions(QUESTION_SET))

        response = self.admin_client.patch(f'/api/v1/system/users/{target.id}/', {
            'password': 'Managed!Pass2026',
        }, format='json')
        self.assertEqual(response.status_code, 400)

        response = self.admin_client.patch(f'/api/v1/system/users/{target.id}/', {
            'password': 'Managed!Pass2026',
            'security_questions': QUESTION_SET,
        }, format='json')
        self.assertEqual(response.status_code, 200)
        target.refresh_from_db()
        self.assertTrue(target.check_password('Managed!Pass2026'))
        self.assertEqual(len(UserProfile.objects.get(user=target).security_questions), 3)

    def test_login_waits_after_five_failures_and_locks_after_ten(self):
        for attempt in range(4):
            response = self.public_client.post('/api/v1/system/login/', {
                'username': self.admin.username,
                'password': f'wrong-{attempt}',
            }, format='json')
            self.assertEqual(response.status_code, 401)

        waiting_response = self.public_client.post('/api/v1/system/login/', {
            'username': self.admin.username,
            'password': 'wrong-fifth',
        }, format='json')
        self.assertEqual(waiting_response.status_code, 429)
        self.assertEqual(waiting_response.data['retry_after'], 120)
        self.assertEqual(waiting_response['Retry-After'], '120')

        profile = UserProfile.objects.get(user=self.admin)
        profile.failed_login_attempts = 9
        profile.login_locked_until = timezone.now() - timedelta(seconds=1)
        profile.save(update_fields=['failed_login_attempts', 'login_locked_until'])
        locked_response = self.public_client.post('/api/v1/system/login/', {
            'username': self.admin.username,
            'password': 'wrong-tenth',
        }, format='json')
        self.assertEqual(locked_response.status_code, 423)
        profile.refresh_from_db()
        self.assertTrue(profile.login_locked)

    def test_forgot_password_resets_password_questions_and_lockout(self):
        profile = UserProfile.objects.get(user=self.admin)
        profile.security_questions = hash_security_questions(QUESTION_SET)
        profile.login_locked = True
        profile.failed_login_attempts = 10
        profile.save(update_fields=['security_questions', 'login_locked', 'failed_login_attempts'])

        questions_response = self.public_client.post('/api/v1/system/forgot-password/questions/', {
            'username': self.admin.username,
        }, format='json')
        self.assertEqual(questions_response.status_code, 200)
        self.assertEqual(len(questions_response.data['questions']), 3)

        replacement_questions = [
            {'question_id': 'favorite_teacher', 'answer': '李老师'},
            {'question_id': 'first_job', 'answer': '档案员'},
            {'question_id': 'favorite_dish', 'answer': '抓饭'},
        ]
        reset_response = self.public_client.post('/api/v1/system/forgot-password/reset/', {
            'username': self.admin.username,
            'answers': QUESTION_SET,
            'new_password': 'Recovered!Pass2026',
            'security_questions': replacement_questions,
        }, format='json')
        self.assertEqual(reset_response.status_code, 200)

        self.admin.refresh_from_db()
        profile.refresh_from_db()
        self.assertTrue(self.admin.check_password('Recovered!Pass2026'))
        self.assertFalse(profile.login_locked)
        self.assertEqual(profile.failed_login_attempts, 0)
        self.assertEqual(len(profile.security_questions), 3)

        login_response = self.public_client.post('/api/v1/system/login/', {
            'username': self.admin.username,
            'password': 'Recovered!Pass2026',
        }, format='json')
        self.assertEqual(login_response.status_code, 200)

    def test_five_wrong_recovery_answers_start_fifteen_minute_wait(self):
        profile = UserProfile.objects.get(user=self.admin)
        profile.security_questions = hash_security_questions(QUESTION_SET)
        profile.save(update_fields=['security_questions'])
        wrong_answers = [
            {'question_id': item['question_id'], 'answer': '错误答案'}
            for item in QUESTION_SET
        ]

        for _ in range(4):
            response = self.public_client.post('/api/v1/system/forgot-password/reset/', {
                'username': self.admin.username,
                'answers': wrong_answers,
                'new_password': 'Recovered!Pass2026',
                'security_questions': QUESTION_SET,
            }, format='json')
            self.assertEqual(response.status_code, 400)

        response = self.public_client.post('/api/v1/system/forgot-password/reset/', {
            'username': self.admin.username,
            'answers': wrong_answers,
            'new_password': 'Recovered!Pass2026',
            'security_questions': QUESTION_SET,
        }, format='json')
        self.assertEqual(response.status_code, 429)
        profile.refresh_from_db()
        self.assertIsNotNone(profile.recovery_locked_until)