from django.core.management import call_command
from django.core.management.base import BaseCommand

from restaurant.models import MenuItem


class Command(BaseCommand):
    help = "Seed the sample restaurant menu only when the database menu is empty."

    def handle(self, *args, **options):
        if MenuItem.objects.exists():
            self.stdout.write("Menu already has items; existing data was left unchanged.")
            return

        call_command("seed_menu", stdout=self.stdout, stderr=self.stderr)