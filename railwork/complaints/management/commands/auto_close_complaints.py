from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from complaints.models import Complaint


class Command(BaseCommand):
    help = 'Auto-close complaints that are not closed after 24 hours'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be closed without actually closing',
        )

    def handle(self, *args, **options):
        # Get complaints older than 24 hours that are not closed
        twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
        
        complaints_to_close = Complaint.objects.filter(
            created_at__lte=twenty_four_hours_ago,
            is_closed=False
        )

        count = complaints_to_close.count()
        
        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING(f'Would close {count} complaints (dry run mode)')
            )
            for complaint in complaints_to_close[:10]:  # Show first 10
                self.stdout.write(f'  - {complaint.complaint_number} ({complaint.status})')
            if count > 10:
                self.stdout.write(f'  ... and {count - 10} more')
        else:
            # Close the complaints
            for complaint in complaints_to_close:
                complaint.is_closed = True
                complaint.closed_at = timezone.now()
                complaint.closed_status = complaint.status
                complaint.save()

            self.stdout.write(
                self.style.SUCCESS(f'Successfully auto-closed {count} complaints')
            ) 