import json
from decimal import Decimal
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from .currency import format_inr
from .management.commands.download_menu_images import image_extension, openverse_image_for, thumbnail_source
from .models import Category, MenuItem, Order, OrderItem


class OrderingFlowTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Main Course")
        self.item = MenuItem.objects.create(
            category=self.category,
            name="Garden Bowl",
            description="Seasonal vegetables and grains.",
            price=Decimal("12.50"),
            is_vegetarian=True,
            is_available=True,
        )

    def test_inr_formatter_uses_indian_grouping(self):
        self.assertEqual(format_inr(Decimal("1000.00")), "₹1,000.00")
        self.assertEqual(format_inr(Decimal("150000.00")), "₹1,50,000.00")

    def test_local_menu_image_path_renders_and_reaches_cart_payload(self):
        self.item.image_path = "images/menu/garden-bowl.jpg"
        self.item.save(update_fields=["image_path"])

        home_response = self.client.get(reverse("restaurant:home"))
        cart_response = self.client.get(reverse("restaurant:cart"))

        self.assertContains(home_response, 'src="/static/images/menu/garden-bowl.jpg"')
        self.assertContains(cart_response, '"image": "/static/images/menu/garden-bowl.jpg"')

    def test_image_downloader_validates_and_skips_existing_files(self):
        self.item.image_url = "https://upload.wikimedia.org/wikipedia/commons/test.jpg"
        self.item.save(update_fields=["image_url"])
        image_bytes = b"\xff\xd8\xff\xe0" + b"test-image-data"
        response = MagicMock()
        response.__enter__.return_value = response
        response.headers.get_content_type.return_value = "image/jpeg"
        response.read.return_value = image_bytes

        with TemporaryDirectory() as temporary_directory:
            with override_settings(BASE_DIR=Path(temporary_directory)):
                with patch(
                    "restaurant.management.commands.download_menu_images.urlopen",
                    return_value=response,
                ) as download:
                    call_command("download_menu_images", stdout=StringIO(), stderr=StringIO())

                self.item.refresh_from_db()
                image_file = Path(temporary_directory) / "static" / self.item.image_path
                self.assertEqual(self.item.image_path, "images/menu/garden-bowl.jpg")
                self.assertEqual(image_file.read_bytes(), image_bytes)
                self.assertEqual(download.call_count, 1)

                with patch(
                    "restaurant.management.commands.download_menu_images.urlopen",
                    side_effect=AssertionError("Existing local image should be skipped."),
                ):
                    call_command("download_menu_images", stdout=StringIO(), stderr=StringIO())

                self.assertEqual(image_file.read_bytes(), image_bytes)

    def test_image_downloader_rejects_non_image_bytes(self):
        with self.assertRaises(ValueError):
            image_extension(b"not an image")

    def test_image_downloader_uses_openverse_fallback_after_source_throttling(self):
        self.item.image_url = "https://upload.wikimedia.org/wikipedia/commons/test.jpg"
        self.item.save(update_fields=["image_url"])
        thumbnail_url = "https://api.openverse.org/v1/images/example/thumb/"
        attribution_url = "https://www.flickr.com/photos/chef/12345"
        api_response = MagicMock()
        api_response.__enter__.return_value = api_response
        api_response.read.return_value = json.dumps(
            {
                "results": [
                    {
                        "source": "flickr",
                        "title": "Garden Bowl",
                        "tags": [],
                        "thumbnail": thumbnail_url,
                        "foreign_landing_url": attribution_url,
                    }
                ]
            }
        ).encode()
        image_response = MagicMock()
        image_response.__enter__.return_value = image_response
        image_response.headers.get_content_type.return_value = "image/jpeg"
        image_response.read.return_value = b"\xff\xd8\xff\xe0fallback-image-data"

        with TemporaryDirectory() as temporary_directory:
            with override_settings(BASE_DIR=Path(temporary_directory)):
                with patch(
                    "restaurant.management.commands.download_menu_images.urlopen",
                    side_effect=[HTTPError(self.item.image_url, 429, "Rate limited", None, None), api_response, image_response],
                ):
                    call_command("download_menu_images", stdout=StringIO(), stderr=StringIO())

                self.item.refresh_from_db()
                self.assertEqual(self.item.image_url, thumbnail_url)
                self.assertEqual(self.item.image_source_url, attribution_url)
                self.assertTrue((Path(temporary_directory) / "static" / self.item.image_path).is_file())

    def test_image_downloader_uses_commons_thumbnail_and_recognizes_avif(self):
        source = "https://upload.wikimedia.org/wikipedia/commons/e/ed/Samosa_4.jpg"
        self.assertEqual(
            thumbnail_source(source),
            "https://upload.wikimedia.org/wikipedia/commons/thumb/e/ed/Samosa_4.jpg/960px-Samosa_4.jpg",
        )
        self.assertEqual(image_extension(b"\x00\x00\x00\x18ftypavif\x00\x00\x00\x00"), ".avif")

    def test_openverse_fallback_tries_verified_dish_alias(self):
        empty_response = MagicMock()
        empty_response.__enter__.return_value = empty_response
        empty_response.read.return_value = b'{"results": []}'
        result = {
            "source": "flickr",
            "title": "Idli with Sambar and Chutney",
            "tags": [{"name": "idli"}],
            "thumbnail": "https://api.openverse.org/v1/images/idli/thumb/",
            "foreign_landing_url": "https://www.flickr.com/photos/creator/idli",
        }
        match_response = MagicMock()
        match_response.__enter__.return_value = match_response
        match_response.read.return_value = json.dumps({"results": [result]}).encode()

        with patch(
            "restaurant.management.commands.download_menu_images.urlopen",
            side_effect=[empty_response, match_response],
        ):
            source = openverse_image_for(MenuItem(name="Idli (2 pieces)"), set(), timeout=1)

        self.assertEqual(source, (result["thumbnail"], result["foreign_landing_url"]))

    def test_indian_menu_seed_is_repeatable_and_keeps_requested_prices(self):
        call_command("seed_menu", stdout=StringIO())
        first_item_count = MenuItem.objects.count()
        call_command("seed_menu", stdout=StringIO())

        self.assertEqual(MenuItem.objects.count(), first_item_count)
        seeded_items = list(MenuItem.objects.exclude(name="Garden Bowl"))
        self.assertEqual(len(seeded_items), 47)
        image_urls = [item.image_url for item in seeded_items]
        self.assertTrue(all(image_urls))
        self.assertEqual(len(image_urls), len(set(image_urls)))
        indian_categories = [
            "Starters",
            "South Indian",
            "North Indian Main Course",
            "Breads and Rice",
            "Snacks and Street Food",
            "Desserts",
            "Beverages",
        ]
        self.assertEqual(Category.objects.filter(name__in=indian_categories).count(), 7)
        self.assertEqual(
            list(Category.objects.filter(name__in=indian_categories).values_list("name", flat=True)),
            indian_categories,
        )
        self.assertEqual(
            MenuItem.objects.filter(category__name__in=indian_categories)
            .exclude(name__in=["Olive Oil Cake", "Dark Chocolate Tart", "House Lemonade", "Cold Brew"])
            .count(),
            39,
        )
        self.assertEqual(
            MenuItem.objects.get(name="Vegetable Samosa").price,
            Decimal("60.00"),
        )
        self.assertEqual(
            MenuItem.objects.get(name="Mutton Biryani").price,
            Decimal("320.00"),
        )
        self.assertEqual(
            MenuItem.objects.get(name="Vegetable Samosa").image_path,
            "images/menu/vegetable-samosa.webp",
        )
        self.assertTrue(MenuItem.objects.get(name="Chicken Momos").image_source_url)
        self.assertTrue(MenuItem.objects.get(name="Pani Puri").image_source_url)
        self.assertContains(self.client.get(reverse("restaurant:home")), "Image source")

        samosa = MenuItem.objects.get(name="Vegetable Samosa")
        samosa.image_path = "images/menu/vegetable-samosa.jpg"
        samosa.image_url = "https://api.openverse.org/v1/images/samosa/thumb/"
        samosa.image_source_url = "https://www.flickr.com/photos/creator/samosa"
        samosa.save(update_fields=["image_path", "image_url", "image_source_url"])
        call_command("seed_menu", stdout=StringIO())
        samosa.refresh_from_db()
        self.assertEqual(samosa.image_path, "images/menu/vegetable-samosa.jpg")
        self.assertEqual(samosa.image_url, "https://api.openverse.org/v1/images/samosa/thumb/")
        self.assertEqual(samosa.image_source_url, "https://www.flickr.com/photos/creator/samosa")

    def test_seed_menu_if_empty_preserves_existing_menu_data(self):
        call_command("seed_menu", if_empty=True, stdout=StringIO())
        self.assertEqual(MenuItem.objects.count(), 1)
        self.item.refresh_from_db()
        self.assertEqual(self.item.price, Decimal("12.50"))
        self.assertEqual(self.item.name, "Garden Bowl")

    def test_ensure_menu_preserves_existing_menu_data(self):
        call_command("ensure_menu", stdout=StringIO())
        self.assertEqual(MenuItem.objects.count(), 1)
        self.item.refresh_from_db()
        self.assertEqual(self.item.price, Decimal("12.50"))

    def test_ensure_menu_seeds_empty_database(self):
        MenuItem.objects.all().delete()

        call_command("ensure_menu", stdout=StringIO())

        self.assertEqual(MenuItem.objects.count(), 47)
        self.assertEqual(
            MenuItem.objects.get(name="Vegetable Samosa").image_path,
            "images/menu/vegetable-samosa.webp",
        )

    def test_checkout_uses_database_price_and_persists_order(self):
        response = self.client.post(
            reverse("restaurant:checkout"),
            {
                "customer_name": "Jamie Guest",
                "phone": "5551234567",
                "email": "jamie@example.com",
                "table_number": "4",
                "cart_json": json.dumps({str(self.item.pk): 2}),
                "price": "0.01",
            },
        )
        order = Order.objects.get()
        order_item = OrderItem.objects.get(order=order)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(order.subtotal, Decimal("25.00"))
        self.assertEqual(order.tax, Decimal("2.00"))
        self.assertEqual(order.total, Decimal("27.00"))
        self.assertEqual(order_item.unit_price, Decimal("12.50"))
        self.assertNotIn("cart", self.client.session)

    def test_checkout_rejects_unavailable_item(self):
        self.item.is_available = False
        self.item.save()
        response = self.client.post(
            reverse("restaurant:checkout"),
            {
                "customer_name": "Jamie Guest",
                "phone": "5551234567",
                "table_number": "4",
                "cart_json": json.dumps({str(self.item.pk): 1}),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.count(), 0)

    def test_checkout_rejects_fractional_quantity(self):
        response = self.client.post(
            reverse("restaurant:checkout"),
            {
                "customer_name": "Jamie Guest",
                "phone": "5551234567",
                "table_number": "4",
                "cart_json": json.dumps({str(self.item.pk): 1.5}),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.count(), 0)

    def test_kitchen_requires_staff_and_can_update_status(self):
        order = Order.objects.create(
            customer_name="Jamie Guest",
            phone="5551234567",
            table_number=4,
        )
        status_url = reverse("restaurant:update_order_status", args=[order.pk])
        self.assertEqual(self.client.get(reverse("restaurant:kitchen")).status_code, 302)
        staff = get_user_model().objects.create_user(username="chef", password="test-password", is_staff=True)
        self.client.force_login(staff)
        response = self.client.post(status_url, {"status": Order.Status.PREPARING})
        order.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(order.status, Order.Status.PREPARING)

    def test_customer_and_staff_pages_render(self):
        MenuItem.objects.create(
            category=self.category,
            name="Seasonal Soup",
            description="Slow-simmered vegetables.",
            price=Decimal("7.00"),
            is_available=False,
        )
        order = Order.objects.create(
            customer_name="Jamie Guest",
            phone="5551234567",
            table_number=4,
        )
        customer_pages = [
            reverse("restaurant:home"),
            reverse("restaurant:cart"),
            reverse("restaurant:checkout"),
            reverse("restaurant:track_order"),
            reverse("restaurant:order_confirmation", args=[order.public_id]),
            f"{reverse('restaurant:track_order')}?order_id={order.public_id}",
        ]
        for page in customer_pages:
            with self.subTest(page=page):
                self.assertEqual(self.client.get(page).status_code, 200)
        home_response = self.client.get(reverse("restaurant:home"))
        self.assertContains(home_response, "Unavailable")
        self.assertContains(home_response, 'id="menu-search"')
        self.assertContains(home_response, "Vegetarian")
        self.assertContains(home_response, "Non-vegetarian")

        staff = get_user_model().objects.create_user(username="chef", password="test-password", is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(reverse("restaurant:kitchen")).status_code, 200)

    def test_custom_404_page_renders_when_debug_is_disabled(self):
        with self.settings(DEBUG=False, ALLOWED_HOSTS=["testserver"]):
            response = self.client.get("/not-a-real-page/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "This page isn't", status_code=404)

    def test_admin_displays_inr_labels_and_indian_grouping(self):
        superuser = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="test-password",
        )
        self.client.force_login(superuser)
        menu_response = self.client.get(reverse("admin:restaurant_menuitem_changelist"))
        self.assertContains(menu_response, "Price (INR)")
        self.assertContains(menu_response, "₹12.50")

        order = Order.objects.create(
            customer_name="Jamie Guest",
            phone="5551234567",
            table_number=4,
            subtotal=Decimal("150000.00"),
            tax=Decimal("12000.00"),
            total=Decimal("162000.00"),
        )
        detail_response = self.client.get(reverse("admin:restaurant_order_change", args=[order.pk]))
        self.assertContains(detail_response, "Amounts (INR)")
        self.assertContains(detail_response, "₹1,50,000.00")
        self.assertContains(detail_response, "Unit price (INR)")