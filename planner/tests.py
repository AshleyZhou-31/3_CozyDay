from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Category, PlanItem
from unittest.mock import Mock, patch
import requests
from django.utils import timezone


class NavigationAndPlanItemDetailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="section1_user",
            password="test-password",
        )
        cls.category = Category.objects.create(
            user=cls.user,
            name="School",
        )
        cls.item = PlanItem.objects.create(
            user=cls.user,
            category=cls.category,
            title="Finish A3 navigation",
            notes="Verify the model-to-template detail flow.",
        )

    def test_home_page_and_navigation_links(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("home"))
        self.assertContains(response, reverse("login"))
        self.assertContains(response, reverse("signup"))

        self.assertNotContains(
            response,
            f'<a href="{reverse("planner:planitem-list")}">Plan Items</a>',
            html=True,
        )
        self.assertNotContains(
            response,
            f'<a href="{reverse("admin:index")}">Admin</a>',
            html=True,
        )

    def test_get_absolute_url_targets_detail_route(self):
        self.assertEqual(
            self.item.get_absolute_url(),
            reverse("planner:planitem-detail", kwargs={"pk": self.item.pk}),
        )


    def test_list_links_to_model_driven_detail_url(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("planner:planitem-list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.item.title)
        self.assertContains(response, self.item.get_absolute_url())

    def test_detail_page_displays_selected_item(self):
        self.client.force_login(self.user)
        response = self.client.get(self.item.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.item.title)
        self.assertContains(response, self.category.name)
        self.assertContains(response, self.item.notes)

    def test_missing_detail_returns_404(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("planner:planitem-detail", kwargs={"pk": 999999})
        )

        self.assertEqual(response.status_code, 404)

class ChartReadyAPITests(TestCase):
    """A4 Part 1: /api/summary/ and the two chart pages/PNG outputs."""

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="part1_user",
            password="test-password",
        )
        cls.school = Category.objects.create(user=cls.user, name="School")
        cls.errands = Category.objects.create(user=cls.user, name="Errands")

        PlanItem.objects.create(
            user=cls.user,
            category=cls.school,
            title="Finish reading",
            scheduled_date="2026-09-24",
        )
        PlanItem.objects.create(
            user=cls.user,
            category=cls.school,
            title="Submit worksheet",
            scheduled_date="2026-09-25",
        )
        PlanItem.objects.create(
            user=cls.user,
            category=cls.errands,
            title="Buy groceries",
            # no scheduled_date on purpose, to confirm it's excluded, not crashed on
        )

    def setUp(self):
        self.client.force_login(self.user)

    def test_category_summary_chart_page_loads(self):
        response = self.client.get(reverse("chart-category-summary"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "chart-category-summary")
        self.assertContains(response, reverse("api-summary"))

    def test_activity_over_time_chart_page_loads(self):
        response = self.client.get(reverse("chart-activity-over-time"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "chart-activity-over-time")
        self.assertContains(response, reverse("api-summary"))

    def test_chart_png_outputs_return_png_content_type(self):
        chart1 = self.client.get(reverse("vega-chart1-png"))
        chart2 = self.client.get(reverse("vega-chart2-png"))

        self.assertEqual(chart1.status_code, 200)
        self.assertEqual(chart1["Content-Type"], "image/png")

        self.assertEqual(chart2.status_code, 200)
        self.assertEqual(chart2["Content-Type"], "image/png")


class ChartReadyAPIEmptyDatabaseTests(TestCase):
    """A4 Part 1: confirm /api/summary/ and chart routes handle an empty database."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="empty_chart_user",
            password="test-password",
        )
        self.client.force_login(self.user)

    def test_api_summary_with_no_data_returns_empty_lists(self):
        response = self.client.get(reverse("api-summary"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["category_counts"], [])
        self.assertEqual(payload["activity_over_time"], [])

    def test_chart_pages_still_load_with_no_data(self):
        self.assertEqual(self.client.get(reverse("chart-category-summary")).status_code, 200)
        self.assertEqual(self.client.get(reverse("chart-activity-over-time")).status_code, 200)

    def test_png_outputs_still_render_with_no_data(self):
        chart1 = self.client.get(reverse("vega-chart1-png"))
        chart2 = self.client.get(reverse("vega-chart2-png"))

        self.assertEqual(chart1.status_code, 200)
        self.assertEqual(chart1["Content-Type"], "image/png")
        self.assertEqual(chart2.status_code, 200)
        self.assertEqual(chart2["Content-Type"], "image/png")

class PlanItemExportAndReportsTests(TestCase):
    """A4 Part 3: CSV export, JSON export, and the reports page."""

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="part3_user", password="test-password",
        )
        cls.school = Category.objects.create(user=cls.user, name="School")
        cls.errands = Category.objects.create(user=cls.user, name="Errands")

        PlanItem.objects.create(
            user=cls.user, category=cls.school, title="Finish reading",
            item_type=PlanItem.ItemType.TASK, is_completed=True,
        )
        PlanItem.objects.create(
            user=cls.user, category=cls.errands, title="Buy groceries",
            item_type=PlanItem.ItemType.TASK, is_completed=False,
        )

    def setUp(self):
        self.client.force_login(self.user)

    def test_csv_export_has_correct_headers_and_rows(self):
        response = self.client.get(reverse("planner:planitem-export-csv"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertTrue(
            response["Content-Disposition"].startswith('attachment; filename="planitems_')
        )
        content = response.content.decode()
        self.assertIn("id,title,item_type,timing", content)
        self.assertIn("Finish reading", content)
        self.assertIn("Buy groceries", content)

    def test_json_export_has_metadata_and_records(self):
        response = self.client.get(reverse("planner:planitem-export-json"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertTrue(
            response["Content-Disposition"].startswith('attachment; filename="planitems_')
        )
        payload = response.json()
        self.assertIn("generated_at", payload)
        self.assertEqual(payload["record_count"], 2)
        titles = {item["title"] for item in payload["plan_items"]}
        self.assertIn("Finish reading", titles)
        self.assertIn("Buy groceries", titles)

    def test_reports_page_shows_summaries_and_totals(self):
        response = self.client.get(reverse("planner:planitem-reports"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "School")
        self.assertContains(response, "Errands")
        self.assertContains(response, reverse("planner:planitem-export-csv"))
        self.assertContains(response, reverse("planner:planitem-export-json"))


class PlanItemExportAndReportsEmptyDatabaseTests(TestCase):
    """A4 Part 3: confirm exports and the reports page handle an empty database."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="empty_reports_user",
            password="test-password",
        )
        self.client.force_login(self.user)

    def test_csv_export_with_no_data_returns_header_only(self):
        response = self.client.get(reverse("planner:planitem-export-csv"))
        content = response.content.decode()
        self.assertEqual(len(content.strip().splitlines()), 1)

    def test_json_export_with_no_data_returns_empty_list(self):
        response = self.client.get(reverse("planner:planitem-export-json"))
        payload = response.json()
        self.assertEqual(payload["record_count"], 0)
        self.assertEqual(payload["plan_items"], [])

    def test_reports_page_with_no_data_shows_empty_state(self):
        response = self.client.get(reverse("planner:planitem-reports"))
        self.assertContains(response, "No categories yet.")
        self.assertContains(response, "No plan items yet.")


class ExternalBookSearchAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="external_api_user",
            password="test-password",
        )

        PlanItem.objects.create(
            user=cls.user,
            title="Study for INFO 490",
        )

    def setUp(self):
        self.client.force_login(self.user)

    @patch("planner.views.requests.get")
    def test_successful_external_query(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = {
            "docs": [
                {
                    "title": "Study Skills",
                    "author_name": ["Example Author"],
                    "first_publish_year": 2020,
                }
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        response = self.client.get(
            reverse("planner:external-book-search-api"),
            {"q": "study"},
        )

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertEqual(data["query"], "study")
        self.assertEqual(len(data["external_results"]), 1)
        self.assertEqual(data["cozyday_match_count"], 1)

        mock_get.assert_called_once_with(
            "https://openlibrary.org/search.json",
            params={"q": "study"},
            timeout=5,
        )

        mock_response.raise_for_status.assert_called_once()

    def test_missing_query(self):
        response = self.client.get(
            reverse("planner:external-book-search-api")
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"],
            "Missing query parameter.",
        )

    @patch("planner.views.requests.get")
    def test_no_results(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = {"docs": []}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        response = self.client.get(
            reverse("planner:external-book-search-api"),
            {"q": "zzzzzz"},
        )

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertEqual(data["external_results"], [])
        self.assertEqual(
            data["message"],
            "No external results found.",
        )

    @patch("planner.views.requests.get")
    def test_timeout_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout

        response = self.client.get(
            reverse("planner:external-book-search-api"),
            {"q": "study"},
        )

        self.assertEqual(response.status_code, 504)
        self.assertEqual(
            response.json()["error"],
            "The external API request timed out.",
        )

    @patch("planner.views.requests.get")
    def test_connection_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError

        response = self.client.get(
            reverse("planner:external-book-search-api"),
            {"q": "study"},
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["error"],
            "Could not connect to the external API.",
        )

    @patch("planner.views.requests.get")
    def test_http_error(self, mock_get):
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = (
            requests.exceptions.HTTPError
        )
        mock_get.return_value = mock_response

        response = self.client.get(
            reverse("planner:external-book-search-api"),
            {"q": "study"},
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["error"],
            "The external API returned an HTTP error.",
        )

    @patch("planner.views.requests.get")
    def test_invalid_json(self, mock_get):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = ValueError
        mock_get.return_value = mock_response

        response = self.client.get(
            reverse("planner:external-book-search-api"),
            {"q": "study"},
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["error"],
            "The external API returned invalid JSON.",
        )


class AuthenticationTests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="auth_user",
            password="test-password",
        )

    def test_signup_creates_user_and_logs_in(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "new_user",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            get_user_model().objects.filter(username="new_user").exists()
        )
        self.assertIn("_auth_user_id", self.client.session)

    def test_duplicate_signup_shows_error(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "auth_user",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "A user with that username already exists.",
        )

    def test_valid_login_succeeds(self):
        response = self.client.post(
            reverse("login"),
            {
                "username": "auth_user",
                "password": "test-password",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

    def test_invalid_login_stays_on_login_page(self):
        response = self.client.post(
            reverse("login"),
            {
                "username": "auth_user",
                "password": "wrong-password",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Please enter a correct username and password",
        )

    def test_logout_ends_session(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("logout"))

        self.assertEqual(response.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_anonymous_user_cannot_open_private_page(self):
        response = self.client.get(reverse("planner:planitem-list"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_authenticated_user_can_open_private_page(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("planner:planitem-list"))

        self.assertEqual(response.status_code, 200)

    def test_authenticated_user_can_open_protected_api(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("api-summary"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")

    def test_navigation_changes_after_login(self):
        anonymous_response = self.client.get(reverse("home"))

        self.assertContains(anonymous_response, reverse("login"))
        self.assertContains(anonymous_response, reverse("signup"))

        self.client.force_login(self.user)

        authenticated_response = self.client.get(reverse("home"))

        self.assertContains(
            authenticated_response,
            reverse("planner:planitem-list"),
        )
        self.assertNotContains(authenticated_response, reverse("admin:index"))
        self.assertContains(authenticated_response, reverse("logout"))

class UserDataIsolationTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user_a = get_user_model().objects.create_user(
            username="user_a",
            password="test-password",
        )
        cls.user_b = get_user_model().objects.create_user(
            username="user_b",
            password="test-password",
        )

        cls.category_a = Category.objects.create(
            user=cls.user_a,
            name="User A Category",
        )
        cls.category_b = Category.objects.create(
            user=cls.user_b,
            name="User B Category",
        )

        cls.item_a = PlanItem.objects.create(
            user=cls.user_a,
            category=cls.category_a,
            title="User A Private Item",
            notes="Only user A should see this.",
            is_completed=True,
        )

        cls.item_b = PlanItem.objects.create(
            user=cls.user_b,
            category=cls.category_b,
            title="User B Secret Item",
            notes="Only user B should see this.",
            is_completed=False,
        )

    def setUp(self):
        self.client.force_login(self.user_a)

    def test_user_cannot_view_other_users_detail_page(self):
        response = self.client.get(self.item_b.get_absolute_url())

        self.assertEqual(response.status_code, 404)

    def test_search_only_returns_logged_in_users_items(self):
        response = self.client.get(
            reverse("planner:planitem-search"),
            {"title": "User"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.item_a.title)
        self.assertNotContains(response, self.item_b.title)

    def test_plan_items_api_only_returns_logged_in_users_items(self):
        response = self.client.get(
            reverse("planner:plan-items-api")
        )

        self.assertEqual(response.status_code, 200)

        titles = {
            item["title"]
            for item in response.json()["results"]
        }

        self.assertIn(self.item_a.title, titles)
        self.assertNotIn(self.item_b.title, titles)

    def test_reports_only_include_logged_in_users_data(self):
        response = self.client.get(
            reverse("planner:planitem-reports")
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.category_a.name)
        self.assertNotContains(response, self.category_b.name)

        self.assertEqual(response.context["total_items"], 1)
        self.assertEqual(response.context["total_completed"], 1)

    def test_csv_export_only_contains_logged_in_users_items(self):
        response = self.client.get(
            reverse("planner:planitem-export-csv")
        )

        self.assertEqual(response.status_code, 200)

        content = response.content.decode("utf-8")

        self.assertIn(self.item_a.title, content)
        self.assertNotIn(self.item_b.title, content)

    def test_json_export_only_contains_logged_in_users_items(self):
        response = self.client.get(
            reverse("planner:planitem-export-json")
        )

        self.assertEqual(response.status_code, 200)

        payload = response.json()
        titles = {
            item["title"]
            for item in payload["plan_items"]
        }

        self.assertEqual(payload["record_count"], 1)
        self.assertIn(self.item_a.title, titles)
        self.assertNotIn(self.item_b.title, titles)

    def test_regular_user_does_not_see_admin_link(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response,
            reverse("admin:index"),
        )

    def test_staff_user_can_see_admin_link(self):
        staff_user = get_user_model().objects.create_user(
            username="staff_user",
            password="test-password",
            is_staff=True,
        )

        self.client.force_login(staff_user)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse("admin:index"),
        )


class PublicApiSummaryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.demo_user = User.objects.create_user(
            username="rishabh_demo", password="demopassword123"
        )
        cls.category = Category.objects.create(
            user=cls.demo_user, name="School", color="#4A90D9"
        )
        PlanItem.objects.create(
            user=cls.demo_user,
            title="Demo task",
            category=cls.category,
            item_type=PlanItem.ItemType.TASK,
            timing=PlanItem.Timing.TODAY,
            scheduled_date=timezone.localdate(),
        )

    def test_anonymous_get_succeeds(self):
        response = self.client.get(reverse("api-summary"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")

    def test_response_structure_uses_real_demo_data(self):
        response = self.client.get(reverse("api-summary"))
        payload = response.json()
        self.assertIn("category_counts", payload)
        self.assertIn("activity_over_time", payload)
        self.assertEqual(payload["category_counts"][0]["name"], "School")
        self.assertEqual(payload["category_counts"][0]["item_count"], 1)

    def test_no_account_identifying_fields_leak(self):
        response = self.client.get(reverse("api-summary"))
        body = response.content.decode()
        self.assertNotIn("user_id", body)
        self.assertNotIn("rishabh_demo", body)

    def test_post_is_rejected(self):
        response = self.client.post(reverse("api-summary"))
        self.assertIn(response.status_code, (403, 405))


class PublicApiSummaryMissingDemoAccountTests(TestCase):
    def test_missing_demo_user_returns_empty_lists_not_an_error(self):
        # No rishabh_demo user exists in this test's isolated database.
        response = self.client.get(reverse("api-summary"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"category_counts": [], "activity_over_time": []},
        )


class ProtectedApisStillRequireLoginTests(TestCase):
    def test_plan_items_api_redirects_anonymous_user_to_login(self):
        response = self.client.get(reverse("planner:plan-items-api"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_reports_page_redirects_anonymous_user_to_login(self):
        response = self.client.get(reverse("planner:planitem-reports"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)
















