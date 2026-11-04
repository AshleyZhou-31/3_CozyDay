from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.urls import reverse


class StageFourHomeAndNavigationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="ashley_ui",
            password="a-secure-test-password",
        )

    def test_anonymous_home_has_clear_account_actions_and_skip_link(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="#main-content"')
        self.assertContains(response, "Organize life, gently.")
        self.assertContains(response, reverse("signup"))
        self.assertContains(response, reverse("login"))
        self.assertNotContains(response, reverse("planner:planitem-list"))

    def test_authenticated_home_has_personalized_primary_actions(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Welcome back, ashley_ui.")
        self.assertContains(response, reverse("planner:planitem-list"))
        self.assertContains(response, reverse("planner:ai-rag-planner"))

    def test_current_navigation_item_is_exposed_to_assistive_technology(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, 'aria-current="page"')


class StageFourAuthenticationPageTests(TestCase):
    def test_login_has_explicit_labels_and_friendly_error_summary(self):
        response = self.client.post(
            reverse("login"),
            {"username": "missing", "password": "incorrect"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'for="id_username"')
        self.assertContains(response, 'for="id_password"')
        self.assertContains(response, 'class="form-alert" role="alert"')
        self.assertContains(response, "We could not log you in.")

    def test_signup_shows_field_labels_and_secondary_login_link(self):
        response = self.client.get(reverse("signup"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'for="id_username"')
        self.assertContains(response, 'for="id_password1"')
        self.assertContains(response, reverse("login"))

    def test_cancelled_oauth_state_uses_a_recovery_action(self):
        request = RequestFactory().get("/accounts/3rdparty/login/cancelled/")
        request.user = get_user_model()()

        html = render_to_string(
            "socialaccount/login_cancelled.html",
            request=request,
        )

        self.assertIn("Google login was cancelled", html)
        self.assertIn(reverse("login"), html)

    def test_failed_oauth_state_uses_an_accessible_alert(self):
        request = RequestFactory().get("/accounts/3rdparty/login/error/")
        request.user = get_user_model()()

        html = render_to_string(
            "socialaccount/authentication_error.html",
            request=request,
        )

        self.assertIn("Google login is temporarily unavailable", html)
        self.assertIn('role="alert"', html)


class StageFourRAGPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="rag_ui_user",
            password="a-secure-test-password",
        )

    def test_rag_form_has_privacy_guidance_and_accessible_label(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("planner:ai-rag-planner"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'for="id_query"')
        self.assertContains(response, "avoid names, addresses, health details")
        self.assertContains(response, "Review retrieved sources", count=0)
