from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from complaints.models import UserProfile, City, Station
from django.db import transaction

class Command(BaseCommand):
    help = 'Create a station manager user with limited permissions'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, help='Username for the new user')
        parser.add_argument('--email', type=str, help='Email for the new user')
        parser.add_argument('--password', type=str, help='Password for the new user')
        parser.add_argument('--first-name', type=str, help='First name for the new user')
        parser.add_argument('--last-name', type=str, help='Last name for the new user')

    def handle(self, *args, **options):
        username = options.get('username') or input('Username: ')
        email = options.get('email') or input('Email: ')
        password = options.get('password') or input('Password: ')
        first_name = options.get('first_name') or input('First name (optional): ')
        last_name = options.get('last_name') or input('Last name (optional): ')

        try:
            with transaction.atomic():
                # Create user with limited permissions (no staff, no superuser)
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    is_staff=False,
                    is_superuser=False
                )
                
                # Create user profile
                user_profile = UserProfile.objects.create(
                    user=user,
                    can_manage_station=True
                )
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully created station manager user: {username} ({email})'
                    )
                )
                self.stdout.write(
                    self.style.WARNING(
                        'This user can now login and create/manage ONE station only.'
                    )
                )
                self.stdout.write(
                    self.style.WARNING(
                        'They will NOT have access to the admin panel.'
                    )
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error creating user: {str(e)}')
            ) 