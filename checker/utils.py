from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.db import transaction
from django.utils import timezone

from .models import ActionLog, DailyBackup


def log_action(actor, action, instance=None, description=''):
    return ActionLog.objects.create(
        actor=actor if getattr(actor, 'is_authenticated', False) else None,
        action=action,
        model_name=instance.__class__.__name__ if instance is not None else '',
        object_id=str(instance.pk) if instance is not None and instance.pk is not None else '',
        description=description,
    )


def get_backup_path(backup):
    backup_dir = Path(getattr(settings, 'BACKUP_DIR', settings.BASE_DIR / 'backups'))
    return backup_dir / backup.file_name


def ensure_daily_backup(reason='', user=None):
    """Create/update one active-day JSON backup.

    This works with SQLite on the local PC and PostgreSQL on Render/Neon.
    On Render free hosting, files in the app folder should be treated as
    temporary, so the admin should download backup files from the Backups page.
    """
    backup_dir = Path(getattr(settings, 'BACKUP_DIR', settings.BASE_DIR / 'backups'))
    backup_dir.mkdir(parents=True, exist_ok=True)

    today = timezone.localdate()
    file_name = f'backup_{today.isoformat()}.json'
    backup_path = backup_dir / file_name
    temp_path = backup_dir / f'.{file_name}.tmp'

    with temp_path.open('w', encoding='utf-8') as out:
        call_command(
            'dumpdata',
            'auth.User',
            'checker',
            indent=2,
            exclude=['checker.DailyBackup'],
            stdout=out,
        )
    temp_path.replace(backup_path)

    with transaction.atomic():
        backup, _created = DailyBackup.objects.update_or_create(
            backup_date=today,
            defaults={
                'file_name': file_name,
                'reason': reason[:200],
                'triggered_by': user if getattr(user, 'is_authenticated', False) else None,
            },
        )

    keep_count = int(getattr(settings, 'BACKUP_KEEP_ACTIVE_DAYS', 10))
    backups = list(DailyBackup.objects.order_by('-backup_date'))
    old_backups = backups[keep_count:]
    for old in old_backups:
        old_path = backup_dir / old.file_name
        if old_path.exists():
            old_path.unlink()
        old.delete()

    return backup
