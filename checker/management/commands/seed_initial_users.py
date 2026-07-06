from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from checker.models import UserProfile


INITIAL_USERS = [
    {
        'username': 'admin',
        'password': '{SmartChecking2026}',
        'display_name': 'Admin',
        'role': UserProfile.ROLE_ADMIN,
        'is_staff': True,
        'is_superuser': True,
    },
    {
        'username': 'kiran',
        'password': '3J3te2@',
        'display_name': 'Kiran',
        'role': UserProfile.ROLE_CHECKER,
        'is_staff': False,
        'is_superuser': False,
    },
    {
        'username': 'Shaista',
        'password': 'o/V3D30',
        'display_name': 'Shaista',
        'role': UserProfile.ROLE_CHECKER,
        'is_staff': False,
        'is_superuser': False,
    },
    {
        'username': 'Naila',
        'password': 'wB888:l',
        'display_name': 'Naila',
        'role': UserProfile.ROLE_CHECKER,
        'is_staff': False,
        'is_superuser': False,
    },
    {
        'username': 'Fawad',
        'password': 'C279l[',
        'display_name': 'Fawad',
        'role': UserProfile.ROLE_TEACHER,
        'is_staff': False,
        'is_superuser': False,
    },
]


class Command(BaseCommand):
    help = (
        'Create initial admin/checker/teacher accounts only for an empty database. '
        'Existing users are not overwritten. Use --create-missing to add missing default users, '
        'or --reset-passwords to restore the default initial users.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-missing',
            action='store_true',
            help='Create any missing initial users without changing existing users.',
        )
        parser.add_argument(
            '--reset-passwords',
            action='store_true',
            help='Reset the initial users back to the default passwords and profile values.',
        )

    def handle(self, *args, **options):
        create_missing = options['create_missing']
        reset_passwords = options['reset_passwords']

        if User.objects.exists() and not create_missing and not reset_passwords:
            self.stdout.write(self.style.WARNING(
                'Users already exist. Seed skipped so admin changes, password resets, and deleted users are preserved.'
            ))
            self.stdout.write(self.style.WARNING(
                'Use --create-missing only if you intentionally want to recreate missing default users.'
            ))
            return

        for item in INITIAL_USERS:
            user, created = User.objects.get_or_create(username=item['username'])

            if created or reset_passwords:
                user.set_password(item['password'])
                user.is_staff = item['is_staff']
                user.is_superuser = item['is_superuser']
                user.is_active = True
                user.save()

            profile, profile_created = UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    'display_name': item['display_name'],
                    'role': item['role'],
                    'initial_password_note': item['password'],
                    'is_active_checker': True,
                },
            )
            if reset_passwords:
                profile.display_name = item['display_name']
                profile.role = item['role']
                profile.initial_password_note = item['password']
                profile.is_active_checker = True
                profile.save()

            if created:
                status = 'created'
            elif reset_passwords:
                status = 'reset'
            elif profile_created:
                status = 'profile created'
            else:
                status = 'already exists; left unchanged'
            self.stdout.write(self.style.SUCCESS(f'{item["username"]}: {status}'))

        self.stdout.write(self.style.SUCCESS('Initial users are ready.'))
