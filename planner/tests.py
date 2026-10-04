from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Category, PlanItem
from unittest.mock import Mock, patch
import requests


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
        self.assertContains(response, reverse("planner:planitem-list"))
        self.assertContains(response, reverse("admin:index"))

    def test_get_absolute_url_targets_detail_route(self):
        self.assertEqual(
            self.item.get_absolute_url(),
            reverse("planner:planitem-detail", kwargs={"pk": self.item.pk}),
        )

    def test_list_links_to_model_driven_detail_url(self):
        response = self.client.get(reverse("planner:planitem-list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.item.title)
        self.assertContains(response, self.item.get_absolute_url())

    def test_detail_page_displays_selected_item(self):
        response = self.client.get(self.item.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.item.title)
        self.assertContains(response, self.category.name)
        self.assertContains(response, self.item.notes)

    def test_missing_detail_returns_404(self):
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

    def test_api_summary_returns_json_with_real_data(self):
        response = self.client.get(reverse("api-summary"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")

        payload = response.json()
        category_names = {row["name"] for row in payload["category_counts"]}
        self.assertIn("School", category_names)
        self.assertIn("Errands", category_names)

        school_row = next(
            row for row in payload["category_counts"] if row["name"] == "School"
        )
        self.assertEqual(school_row["item_count"], 2)

        # Only the two dated items should appear; the undated one is excluded.
        self.assertEqual(len(payload["activity_over_time"]), 2)
        for row in payload["activity_over_time"]:
            self.assertIn("date", row)
            self.assertIn("count", row)

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