from django.core.management.base import BaseCommand

from core.models import Destination, Problem
from core.seed_data import DESTINATIONS, PROBLEMS


class Command(BaseCommand):
    help = "Load starter destinations and travel problems (safe to run more than once)."

    def handle(self, *args, **options):
        for slug, name, place, category, blurb, description, tip, featured in DESTINATIONS:
            Destination.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": name, "place": place, "category": category, "blurb": blurb,
                    "description": description, "travel_tip": tip, "featured": featured,
                },
            )
        for item in PROBLEMS:
            slug = item["slug"]
            defaults = {k: v for k, v in item.items() if k != "slug"}
            Problem.objects.update_or_create(slug=slug, defaults=defaults)
        self.stdout.write(self.style.SUCCESS(
            f"Loaded {len(DESTINATIONS)} destinations and {len(PROBLEMS)} problems."
        ))
