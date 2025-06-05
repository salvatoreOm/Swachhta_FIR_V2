from django.core.management.base import BaseCommand
from complaints.models import PlatformLocation


class Command(BaseCommand):
    help = 'Update hash IDs from old format (P11, P12) to new format ((1/1), (1/2))'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without actually updating',
        )

    def handle(self, *args, **options):
        locations = PlatformLocation.objects.all().order_by('station', 'platform_number', 'id')
        
        updated_count = 0
        
        for location in locations:
            old_hash_id = location.hash_id
            
            # Skip if already in new format
            if old_hash_id.startswith('(') and old_hash_id.endswith(')'):
                continue
                
            # Calculate new hash_id
            existing_count = PlatformLocation.objects.filter(
                station=location.station,
                platform_number=location.platform_number,
                id__lt=location.id  # Only count locations created before this one
            ).count()
            
            sequence = existing_count + 1
            new_hash_id = f"({location.platform_number}/{sequence})"
            
            if options['dry_run']:
                self.stdout.write(f'Would update {old_hash_id} -> {new_hash_id} for {location}')
            else:
                location.hash_id = new_hash_id
                location.save(update_fields=['hash_id'])
                self.stdout.write(f'Updated {old_hash_id} -> {new_hash_id} for {location}')
            
            updated_count += 1
        
        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING(f'Would update {updated_count} hash IDs (dry run mode)')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'Successfully updated {updated_count} hash IDs')
            ) 