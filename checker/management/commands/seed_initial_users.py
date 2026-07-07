from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from checker.models import UserProfile


ADMIN_USER = {
    'username': 'admin',
    'password': '{SmartChecking2026}',
    'display_name': 'Admin',
    'role': UserProfile.ROLE_ADMIN,
    'is_staff': True,
    'is_superuser': True,
}


class Command(BaseCommand):
    help = 'Create only the first admin account when the database has no users. Existing users are never overwritten.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset-admin-password',
            action='store_true',
            help='Reset the admin password only if the admin user exists. Use carefully.',
        )

    def handle(self, *args, **options):
        reset_admin = options['reset_admin_password']

        if User.objects.exists() and not reset_admin:
            self.stdout.write(self.style.WARNING(
                'Users already exist. Seed skipped. No passwords or deleted users were restored.'
            ))
            return

        item = ADMIN_USER
        user, created = User.objects.get_or_create(username=item['username'])

        if created or reset_admin:
            user.set_password(item['password'])
            user.is_staff = item['is_staff']
            user.is_superuser = item['is_superuser']
            user.is_active = True
            user.save()

        profile, _profile_created = UserProfile.objects.get_or_create(
            user=user,
            defaults={
                'display_name': item['display_name'],
                'role': item['role'],
                'initial_password_note': item['password'],
                'is_active_checker': True,
            },
        )
        if reset_admin:
            profile.display_name = item['display_name']
            profile.role = item['role']
            profile.initial_password_note = item['password']
            profile.is_active_checker = True
            profile.save()

        status = 'created' if created else 'admin password reset' if reset_admin else 'ready'
        self.stdout.write(self.style.SUCCESS(f'{item["username"]}: {status}'))
