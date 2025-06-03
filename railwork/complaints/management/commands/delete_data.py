from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from complaints.models import *
from django.db import transaction

class Command(BaseCommand):
    help = 'Delete data from the database'

    def add_arguments(self, parser):
        parser.add_argument('--all-data', action='store_true', help='Delete all complaints app data')
        parser.add_argument('--all-complaints', action='store_true', help='Delete all complaints only')
        parser.add_argument('--user', type=str, help='Delete specific user by username')
        parser.add_argument('--station', type=str, help='Delete specific station by code')
        parser.add_argument('--city', type=str, help='Delete specific city by code')
        parser.add_argument('--non-superusers', action='store_true', help='Delete all non-superuser accounts')

    def handle(self, *args, **options):
        if options['all_data']:
            self.delete_all_data()
        elif options['all_complaints']:
            self.delete_all_complaints()
        elif options['user']:
            self.delete_user(options['user'])
        elif options['station']:
            self.delete_station(options['station'])
        elif options['city']:
            self.delete_city(options['city'])
        elif options['non_superusers']:
            self.delete_non_superusers()
        else:
            self.stdout.write(self.style.ERROR('Please specify what to delete. Use --help for options.'))

    def delete_all_data(self):
        try:
            with transaction.atomic():
                # Delete in correct order due to foreign keys
                ComplaintPhoto.objects.all().delete()
                OTPVerification.objects.all().delete()
                Complaint.objects.all().delete()
                PlatformLocation.objects.all().delete()
                UserProfile.objects.all().delete()
                Station.objects.all().delete()
                City.objects.all().delete()
                
                self.stdout.write(self.style.SUCCESS('All complaints app data deleted successfully!'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error deleting data: {str(e)}'))

    def delete_all_complaints(self):
        try:
            with transaction.atomic():
                photo_count = ComplaintPhoto.objects.count()
                otp_count = OTPVerification.objects.count()
                complaint_count = Complaint.objects.count()
                
                ComplaintPhoto.objects.all().delete()
                OTPVerification.objects.all().delete()
                Complaint.objects.all().delete()
                
                self.stdout.write(self.style.SUCCESS(
                    f'Deleted {complaint_count} complaints, {photo_count} photos, {otp_count} OTP records'
                ))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error deleting complaints: {str(e)}'))

    def delete_user(self, username):
        try:
            user = User.objects.get(username=username)
            user.delete()
            self.stdout.write(self.style.SUCCESS(f'User "{username}" and all related data deleted!'))
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'User "{username}" not found'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error deleting user: {str(e)}'))

    def delete_station(self, station_code):
        try:
            station = Station.objects.get(station_code=station_code)
            station_name = station.name
            station.delete()
            self.stdout.write(self.style.SUCCESS(f'Station "{station_name}" ({station_code}) and all related data deleted!'))
        except Station.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Station with code "{station_code}" not found'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error deleting station: {str(e)}'))

    def delete_city(self, city_code):
        try:
            city = City.objects.get(code=city_code)
            city_name = city.name
            city.delete()
            self.stdout.write(self.style.SUCCESS(f'City "{city_name}" ({city_code}) and all related data deleted!'))
        except City.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'City with code "{city_code}" not found'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error deleting city: {str(e)}'))

    def delete_non_superusers(self):
        try:
            users = User.objects.filter(is_superuser=False)
            count = users.count()
            users.delete()
            self.stdout.write(self.style.SUCCESS(f'Deleted {count} non-superuser accounts and all related data!'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error deleting users: {str(e)}')) 