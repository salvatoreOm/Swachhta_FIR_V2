from django.core.management.base import BaseCommand
from complaints.models import LocationType

class Command(BaseCommand):
    help = 'Creates initial location types for platform QR codes'

    def handle(self, *args, **kwargs):
        location_types = [
            'Platform End (Side 1)',
            'Platform End (Side 2)',
            'Near Washroom',
            'Entrance Gate',
            'Waiting Area',
            'Food Court',
            'Ticket Counter',
            'Information Desk',
            'Platform Middle',
            'Foot Over Bridge',
        ]

        for location in location_types:
            LocationType.objects.get_or_create(name=location)
            self.stdout.write(self.style.SUCCESS(f'Successfully created location type "{location}"')) 