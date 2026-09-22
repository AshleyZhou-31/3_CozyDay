from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Category, PlanItem


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
