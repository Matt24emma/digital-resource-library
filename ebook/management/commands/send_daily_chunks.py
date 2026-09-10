from django.core.management.base import BaseCommand
from ebook.tasks import send_daily_chunks


class Command(BaseCommand):
    help = "Send daily reading chunks to premium users"

    def handle(self, *args, **options):
        result = send_daily_chunks()
        self.stdout.write(self.style.SUCCESS(result))
