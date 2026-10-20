from django.test import TestCase
from django.urls import reverse


class HomePageSmokeTest(TestCase):
    def test_home_page_returns_200(self):
        """Smoke test verifying home/landing page renders with HTTP 200."""
        response = self.client.get(reverse('dashboard:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Academic Project Monitoring & Evaluation')
        self.assertTemplateUsed(response, 'dashboard/home.html')
        self.assertTemplateUsed(response, 'base.html')
