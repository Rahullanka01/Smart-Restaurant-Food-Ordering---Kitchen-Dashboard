from pathlib import Path
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from restaurant.models import Category, MenuItem


VERIFIED_IMAGE_SOURCES = {
    "Vegetable Samosa": (
        "https://upload.wikimedia.org/wikipedia/commons/e/ed/Samosa_4.jpg",
        "https://commons.wikimedia.org/wiki/File:Samosa_4.jpg",
    ),
    "Chicken Momos": (
        "https://upload.wikimedia.org/wikipedia/commons/0/05/Chicken_Momo_-_Howrah_2013-10-10_3254.JPG",
        "https://commons.wikimedia.org/wiki/File:Chicken_Momo_-_Howrah_2013-10-10_3254.JPG",
    ),
    "Veg Momos": (
        "https://upload.wikimedia.org/wikipedia/commons/5/52/Vegetable_Momos_-_Yak_Yeti_Yak_2025-07-23.jpg",
        "https://commons.wikimedia.org/wiki/File:Vegetable_Momos_-_Yak_Yeti_Yak_2025-07-23.jpg",
    ),
    "Pani Puri": (
        "https://upload.wikimedia.org/wikipedia/commons/5/5c/Crispy_Pani_Puri.jpg",
        "https://commons.wikimedia.org/wiki/File:Crispy_Pani_Puri.jpg",
    ),
    "Pav Bhaji": (
        "https://upload.wikimedia.org/wikipedia/commons/6/63/Pav_Bhaji.jpg",
        "https://commons.wikimedia.org/wiki/File:Pav_Bhaji.jpg",
    ),
    "Vada Pav": (
        "https://upload.wikimedia.org/wikipedia/commons/4/4d/Crunchy_Crispy_Vada_pav.jpg",
        "https://commons.wikimedia.org/wiki/File:Crunchy_Crispy_Vada_pav.jpg",
    ),
    "Aloo Tikki Chaat": (
        "https://upload.wikimedia.org/wikipedia/commons/a/a3/Aloo_Mutter_tikki_chaat_%281%29.JPG",
        "https://commons.wikimedia.org/wiki/File:Aloo_Mutter_tikki_chaat_%281%29.JPG",
    ),
    "Andhra Chicken Fry": (
        "https://upload.wikimedia.org/wikipedia/commons/9/96/Andhra_Fried_Chicken.JPG",
        "https://commons.wikimedia.org/wiki/File:Andhra_Fried_Chicken.JPG",
    ),
    "Paneer Butter Masala": (
        "https://upload.wikimedia.org/wikipedia/commons/7/7e/Paneer_Butter_Masala_3.jpg",
        "https://commons.wikimedia.org/wiki/File:Paneer_Butter_Masala_3.jpg",
    ),
    "Idli (2 pieces)": (
        "https://upload.wikimedia.org/wikipedia/commons/0/02/Idli_Sambar-Noida-UP-SP004.jpg",
        "https://commons.wikimedia.org/wiki/File:Idli_Sambar-Noida-UP-SP004.jpg",
    ),
    "Medu Vada": (
        "https://upload.wikimedia.org/wikipedia/commons/0/06/%E0%B4%89%E0%B4%B4%E0%B5%81%E0%B4%A8%E0%B5%8D%E0%B4%A8%E0%B5%81%E0%B4%B5%E0%B4%9F%E0%B4%95%E0%B5%BE.JPG",
        "https://commons.wikimedia.org/wiki/File:%E0%B4%89%E0%B4%B4%E0%B5%81%E0%B4%A8%E0%B5%8D%E0%B4%A8%E0%B5%81%E0%B4%B5%E0%B4%9F%E0%B4%95%E0%B5%BE.JPG",
    ),
    "Masala Dosa": (
        "https://upload.wikimedia.org/wikipedia/commons/4/43/Masala_dosa_01.jpg",
        "https://commons.wikimedia.org/wiki/File:Masala_dosa_01.jpg",
    ),
    "Mysore Masala Dosa": (
        "https://upload.wikimedia.org/wikipedia/commons/d/d9/Mysore_masala_dosa_in_Mysuru%2C_July_2013.jpg",
        "https://commons.wikimedia.org/wiki/File:Mysore_masala_dosa_in_Mysuru,_July_2013.jpg",
    ),
    "Plain Dosa": (
        "https://upload.wikimedia.org/wikipedia/commons/f/f7/Dosa_%28South_Indian_cuisine%29.jpg",
        "https://commons.wikimedia.org/wiki/File:Dosa_(South_Indian_cuisine).jpg",
    ),
    "Andhra Chicken Curry": (
        "https://upload.wikimedia.org/wikipedia/commons/7/7f/Andhra_Chicken_Curry_-_WCI-Day0-Dinner.jpg",
        "https://commons.wikimedia.org/wiki/File:Andhra_Chicken_Curry_-_WCI-Day0-Dinner.jpg",
    ),
    "Butter Chicken": (
        "https://upload.wikimedia.org/wikipedia/commons/f/fb/Butter_Chicken%2C_City_Grill_Kottayam.jpg",
        "https://commons.wikimedia.org/wiki/File:Butter_Chicken,_City_Grill_Kottayam.jpg",
    ),
    "Butter Naan": (
        "https://upload.wikimedia.org/wikipedia/commons/8/8f/Butter_Naan_with_three_different_Indian_curry.jpg",
        "https://commons.wikimedia.org/wiki/File:Butter_Naan_with_three_different_Indian_curry.jpg",
    ),
    "Garlic Naan": (
        "https://upload.wikimedia.org/wikipedia/commons/8/81/Garlic_naan_1.jpg",
        "https://commons.wikimedia.org/wiki/File:Garlic_naan_1.jpg",
    ),
    "Tandoori Roti": (
        "https://upload.wikimedia.org/wikipedia/commons/5/56/Tandoori_Roti_in_clay_oven.JPG",
        "https://commons.wikimedia.org/wiki/File:Tandoori_Roti_in_clay_oven.JPG",
    ),
    "Chicken Biryani": (
        "https://live.staticflickr.com/2336/2182870752_080dbcaf8c_b.jpg",
        "https://www.flickr.com/photos/87232391@N00/2182870752",
    ),
    "Mutton Biryani": (
        "https://upload.wikimedia.org/wikipedia/commons/2/23/A_home_made_plate_of_mutton_biryani_served_with_chicken_kassa_cooked_in_the_bengali_style.jpg",
        "https://commons.wikimedia.org/wiki/File:A_home_made_plate_of_mutton_biryani_served_with_chicken_kassa_cooked_in_the_bengali_style.jpg",
    ),
    "Veg Biryani": (
        "https://upload.wikimedia.org/wikipedia/commons/2/2f/Veg_biryani.jpg",
        "https://commons.wikimedia.org/wiki/File:Veg_biryani.jpg",
    ),
    "Dal Tadka": (
        "https://upload.wikimedia.org/wikipedia/commons/f/f0/Dal_Tadka-Delhi.jpg",
        "https://commons.wikimedia.org/wiki/File:Dal_Tadka-Delhi.jpg",
    ),
    "Jeera Rice": (
        "https://upload.wikimedia.org/wikipedia/commons/5/5e/Jeera-rice.JPG",
        "https://commons.wikimedia.org/wiki/File:Jeera-rice.JPG",
    ),
    "Plain Rice": (
        "https://upload.wikimedia.org/wikipedia/commons/c/ce/Plain_white_rice-min-min.jpg",
        "https://commons.wikimedia.org/wiki/File:Plain_white_rice-min-min.jpg",
    ),
    "Gajar Ka Halwa": (
        "https://upload.wikimedia.org/wikipedia/commons/9/96/Delicious_Gajar_Ka_Halwa.jpg",
        "https://commons.wikimedia.org/wiki/File:Delicious_Gajar_Ka_Halwa.jpg",
    ),
    "Gulab Jamun": (
        "https://upload.wikimedia.org/wikipedia/commons/5/58/Two_Gulab_Jamun_in_a_plate_01.jpg",
        "https://commons.wikimedia.org/wiki/File:Two_Gulab_Jamun_in_a_plate_01.jpg",
    ),
    "Kulfi": (
        "https://upload.wikimedia.org/wikipedia/commons/e/ea/Kulfi_ice-cream.jpg",
        "https://commons.wikimedia.org/wiki/File:Kulfi_ice-cream.jpg",
    ),
    "Rasmalai": (
        "https://upload.wikimedia.org/wikipedia/commons/1/10/Rasmalai_3.jpg",
        "https://commons.wikimedia.org/wiki/File:Rasmalai_3.jpg",
    ),
    "Filter Coffee": (
        "https://live.staticflickr.com/3724/10533616393_46a938e1cf_b.jpg",
        "https://www.flickr.com/photos/12505664@N00/10533616393",
    ),
    "Fresh Lime Soda": (
        "https://live.staticflickr.com/182/434942173_4e2c027a02_b.jpg",
        "https://www.flickr.com/photos/23648747@N00/434942173",
    ),
    "House Lemonade": (
        "https://live.staticflickr.com/3072/2881834960_b744c2c38c_b.jpg",
        "https://www.flickr.com/photos/17425845@N00/2881834960",
    ),
    "Mango Lassi": (
        "https://live.staticflickr.com/2752/4142353694_e5697e154a_b.jpg",
        "https://www.flickr.com/photos/37238219@N00/4142353694",
    ),
    "Sweet Lassi": (
        "https://live.staticflickr.com/203/440401976_f462491ffa_b.jpg",
        "https://www.flickr.com/photos/21063397@N00/440401976",
    ),
}


class Command(BaseCommand):
    help = "Create or update the Tastique and Indian restaurant menus."

    def add_arguments(self, parser):
        parser.add_argument(
            "--if-empty",
            action="store_true",
            help="Leave an existing menu untouched; seed only when no menu items exist.",
        )

    def handle(self, *args, **options):
        if options["if_empty"] and MenuItem.objects.exists():
            self.stdout.write("Menu already has items; existing data was left unchanged.")
            return

        samples = [
            ("Starters", 1, [
                ("Vegetable Samosa", "Crisp pastry filled with spiced potatoes and peas.", "60.00", True, "photo-1601050690597-df0568f70950"),
                ("Paneer Tikka", "Char-grilled paneer with peppers and house spices.", "180.00", True, "photo-1567188040759-fb8a883dc6d8"),
                ("Chicken Tikka", "Tandoor-roasted chicken marinated in yogurt and spices.", "220.00", False, "photo-1555939594-58d7cb561ad1"),
                ("Onion Pakoda", "Crisp onion fritters with coriander and green chutney.", "100.00", True, "photo-1625944525533-473f1a3d54e7"),
                ("Gobi Manchurian", "Crispy cauliflower tossed in a tangy Indo-Chinese sauce.", "160.00", True, "photo-1626082927389-6cd097cdc6ec"),
            ]),
            ("South Indian", 2, [
                ("Plain Dosa", "Golden, crisp rice-and-lentil crepe with sambar and chutneys.", "80.00", True, "photo-1630383249896-424e482df921"),
                ("Masala Dosa", "Crisp dosa filled with seasoned potato masala.", "110.00", True, "photo-1630383249896-424e482df921"),
                ("Idli (2 pieces)", "Two soft steamed rice cakes with sambar and chutneys.", "50.00", True, "photo-1589301760014-d929f3979dbc"),
                ("Medu Vada", "Crisp lentil fritters served with sambar and coconut chutney.", "60.00", True, "photo-1589301760014-d929f3979dbc"),
                ("Mysore Masala Dosa", "Spiced red chutney, potato masala, and a crisp dosa.", "130.00", True, "photo-1630383249896-424e482df921"),
                ("Andhra Chicken Fry", "Fiery Andhra-style chicken with curry leaves and black pepper.", "240.00", False, "photo-1555939594-58d7cb561ad1"),
            ]),
            ("North Indian Main Course", 3, [
                ("Paneer Butter Masala", "Paneer in a silky tomato, butter, and cashew gravy.", "220.00", True, "photo-1567188040759-fb8a883dc6d8"),
                ("Dal Tadka", "Yellow lentils finished with cumin, garlic, and ghee.", "150.00", True, "photo-1585937421612-70a008356fbe"),
                ("Chole Bhature", "Punjabi chickpea curry with fluffy fried bread.", "140.00", True, "photo-1585937421612-70a008356fbe"),
                ("Butter Chicken", "Tandoori chicken in a creamy tomato makhani sauce.", "280.00", False, "photo-1603894584373-5ac82b2ae398"),
                ("Chicken Biryani", "Fragrant basmati rice layered with spiced chicken.", "220.00", False, "photo-1563379091339-03246963d96c"),
                ("Veg Biryani", "Basmati rice slow-cooked with garden vegetables and spices.", "160.00", True, "photo-1563379091339-03246963d96c"),
                ("Mutton Biryani", "Aromatic dum biryani with tender, spice-marinated mutton.", "320.00", False, "photo-1563379091339-03246963d96c"),
                ("Andhra Chicken Curry", "Andhra-style chicken curry with a bold chilli finish.", "260.00", False, "photo-1603894584373-5ac82b2ae398"),
            ]),
            ("Breads and Rice", 4, [
                ("Butter Naan", "Soft tandoor-baked naan brushed with butter.", "45.00", True, "photo-1603894584373-5ac82b2ae398"),
                ("Tandoori Roti", "Whole-wheat roti baked fresh in the tandoor.", "25.00", True, "photo-1603894584373-5ac82b2ae398"),
                ("Plain Rice", "Steamed long-grain basmati rice.", "90.00", True, "photo-1585937421612-70a008356fbe"),
                ("Jeera Rice", "Basmati rice tempered with cumin and herbs.", "120.00", True, "photo-1585937421612-70a008356fbe"),
                ("Garlic Naan", "Tandoor-baked naan topped with garlic and coriander.", "60.00", True, "photo-1603894584373-5ac82b2ae398"),
            ]),
            ("Snacks and Street Food", 5, [
                ("Pav Bhaji", "Mumbai-style mashed vegetable curry with buttered pav.", "120.00", True, "photo-1601050690597-df0568f70950"),
                ("Pani Puri", "Crisp puris with potato, chickpeas, and tangy spiced water.", "60.00", True, "photo-1601050690597-df0568f70950"),
                ("Vada Pav", "Spiced potato fritter in a soft bun with chutneys.", "50.00", True, "photo-1601050690597-df0568f70950"),
                ("Aloo Tikki Chaat", "Crisp potato patties topped with yogurt and chutneys.", "90.00", True, "photo-1601050690597-df0568f70950"),
                ("Veg Momos", "Steamed vegetable dumplings with chilli dip.", "100.00", True, "photo-1601050690597-df0568f70950"),
                ("Chicken Momos", "Steamed chicken dumplings with house chilli dip.", "140.00", False, "photo-1601050690597-df0568f70950"),
            ]),
            ("Desserts", 6, [
                ("Gulab Jamun", "Warm milk dumplings soaked in cardamom syrup.", "70.00", True, "photo-1578985545062-69928b1d9587"),
                ("Rasmalai", "Soft paneer dumplings in chilled saffron milk.", "100.00", True, "photo-1578985545062-69928b1d9587"),
                ("Gajar Ka Halwa", "Slow-cooked carrot pudding with nuts and cardamom.", "90.00", True, "photo-1578985545062-69928b1d9587"),
                ("Kulfi", "Traditional slow-frozen Indian milk dessert.", "60.00", True, "photo-1578985545062-69928b1d9587"),
                ("Olive Oil Cake", "Candied citrus, softly whipped cream.", "9.00", True, "photo-1578985545062-69928b1d9587"),
                ("Dark Chocolate Tart", "Sea salt, toasted hazelnut, crème fraîche.", "10.00", True, "photo-1488477181946-6428a0291777"),
            ]),
            ("Beverages", 7, [
                ("Masala Chai", "Freshly brewed tea with warming Indian spices.", "30.00", True, "photo-1571934811356-5cc061b6821f"),
                ("Filter Coffee", "South Indian filter coffee with frothy milk.", "40.00", True, "photo-1461023058943-07fcbe16d735"),
                ("Sweet Lassi", "Chilled yogurt drink, lightly sweetened.", "70.00", True, "photo-1513558161293-c780c0db2b86"),
                ("Mango Lassi", "Ripe mango blended with creamy yogurt.", "90.00", True, "photo-1513558161293-c780c0db2b86"),
                ("Fresh Lime Soda", "Fresh lime, soda, and a choice of sweet or salted.", "50.00", True, "photo-1513558161293-c780c0db2b86"),
                ("House Lemonade", "Fresh lemon, garden mint, a little sparkle.", "5.00", True, "photo-1513558161293-c780c0db2b86"),
                ("Cold Brew", "Slow-steeped coffee, served over ice.", "5.50", True, "photo-1461023058943-07fcbe16d735"),
            ]),
            ("Appetizers", 8, [
                ("Whipped Ricotta Toast", "Honey, thyme, grilled country bread.", "8.50", True, "photo-1509440159596-0249088772ff"),
                ("Crispy Calamari", "Lemon, parsley, and a bright tomato dip.", "12.00", False, "photo-1599487488170-d11ec9c172f0"),
            ]),
            ("Main Course", 9, [
                ("Wild Mushroom Risotto", "Slow-stirred arborio, parmesan, fresh herbs.", "19.00", True, "photo-1476124369491-e7addf5db371"),
                ("Roasted Salmon", "Citrus butter, market greens, crispy potatoes.", "24.00", False, "photo-1467003909585-2f8a72700288"),
            ]),
        ]
        for category_name, order, items in samples:
            category, _ = Category.objects.update_or_create(
                name=category_name,
                defaults={"display_order": order, "description": f"{category_name} from our seasonal kitchen."},
            )
            for name, description, price, vegetarian, image_id in items:
                image_url, image_source_url = VERIFIED_IMAGE_SOURCES.get(
                    name,
                    (f"https://images.unsplash.com/{image_id}?auto=format&fit=crop&w=900&q=82", ""),
                )
                existing_item = MenuItem.objects.filter(name=name).first()
                if existing_item and existing_item.image_path:
                    image_url = existing_item.image_url
                    image_source_url = existing_item.image_source_url
                local_image_path = existing_item.image_path if existing_item else ""
                if not local_image_path:
                    image_slug = slugify(name)
                    image_directory = Path(settings.BASE_DIR) / "static" / "images" / "menu"
                    for extension in (".avif", ".webp", ".jpg", ".jpeg", ".png"):
                        if (image_directory / f"{image_slug}{extension}").is_file():
                            local_image_path = f"images/menu/{image_slug}{extension}"
                            break
                MenuItem.objects.update_or_create(
                    name=name,
                    defaults={
                        "category": category,
                        "description": description,
                        "price": Decimal(price),
                        "is_vegetarian": vegetarian,
                        "is_available": True,
                        "image_url": image_url,
                        "image_path": local_image_path,
                        "image_source_url": image_source_url,
                    },
                )
        self.stdout.write(self.style.SUCCESS("Indian menu and original sample dishes are ready."))