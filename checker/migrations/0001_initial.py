# Generated manually for Smart Copy Checking starter app.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ClassRoom',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=80)),
                ('section', models.CharField(blank=True, max_length=50)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={'ordering': ['name', 'section']},
        ),
        migrations.CreateModel(
            name='Subject',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='ActionLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(max_length=80)),
                ('model_name', models.CharField(blank=True, max_length=80)),
                ('object_id', models.CharField(blank=True, max_length=80)),
                ('description', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='DailyBackup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('backup_date', models.DateField(unique=True)),
                ('file_name', models.CharField(max_length=255)),
                ('reason', models.CharField(blank=True, max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('triggered_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-backup_date']},
        ),
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('display_name', models.CharField(max_length=120)),
                ('role', models.CharField(choices=[('admin', 'Admin'), ('checker', 'Checker')], default='checker', max_length=20)),
                ('initial_password_note', models.CharField(blank=True, max_length=120)),
                ('is_active_checker', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='checker_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['display_name']},
        ),
        migrations.CreateModel(
            name='ClassSubject',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('chapter_count', models.PositiveIntegerField(default=1)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('classroom', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='class_subjects', to='checker.classroom')),
                ('subject', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='class_subjects', to='checker.subject')),
            ],
            options={'ordering': ['classroom__name', 'classroom__section', 'subject__name']},
        ),
        migrations.CreateModel(
            name='Student',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('roll_no', models.CharField(max_length=30)),
                ('full_name', models.CharField(max_length=120)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('classroom', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='students', to='checker.classroom')),
            ],
            options={'ordering': ['classroom__name', 'classroom__section', 'roll_no', 'full_name']},
        ),
        migrations.CreateModel(
            name='ClassSubjectChapter',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('number', models.PositiveIntegerField()),
                ('is_active', models.BooleanField(default=True)),
                ('class_subject', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chapters', to='checker.classsubject')),
            ],
            options={'ordering': ['class_subject__classroom__name', 'class_subject__classroom__section', 'class_subject__subject__name', 'number']},
        ),
        migrations.CreateModel(
            name='CopyCheckRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('checked', 'Checked'), ('not_checked', 'Not Checked'), ('absent', 'Absent'), ('not_submitted', 'Copy Not Submitted'), ('incomplete', 'Incomplete')], default='checked', max_length=30)),
                ('remarks', models.TextField(blank=True)),
                ('actual_checker_name', models.CharField(blank=True, help_text='Use this when someone else checked the copy or has no login account.', max_length=120)),
                ('locked', models.BooleanField(default=False)),
                ('locked_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('actual_checker_user', models.ForeignKey(blank=True, help_text='Use this when the actual checker has a login account.', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='actual_copy_records', to=settings.AUTH_USER_MODEL)),
                ('chapter', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='copy_records', to='checker.classsubjectchapter')),
                ('class_subject', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='copy_records', to='checker.classsubject')),
                ('classroom', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='copy_records', to='checker.classroom')),
                ('entered_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='entered_copy_records', to=settings.AUTH_USER_MODEL)),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='copy_records', to='checker.student')),
            ],
            options={'ordering': ['-locked_at', 'student__full_name']},
        ),
        migrations.CreateModel(
            name='CorrectionRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.TextField()),
                ('requested_status', models.CharField(blank=True, choices=[('checked', 'Checked'), ('not_checked', 'Not Checked'), ('absent', 'Absent'), ('not_submitted', 'Copy Not Submitted'), ('incomplete', 'Incomplete')], max_length=30)),
                ('requested_remarks', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending', max_length=20)),
                ('admin_note', models.TextField(blank=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('record', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='correction_requests', to='checker.copycheckrecord')),
                ('requested_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='correction_requests', to=settings.AUTH_USER_MODEL)),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='reviewed_correction_requests', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddConstraint(
            model_name='classroom',
            constraint=models.UniqueConstraint(fields=('name', 'section'), name='unique_class_section'),
        ),
        migrations.AddConstraint(
            model_name='classsubject',
            constraint=models.UniqueConstraint(fields=('classroom', 'subject'), name='unique_subject_per_class'),
        ),
        migrations.AddConstraint(
            model_name='student',
            constraint=models.UniqueConstraint(fields=('classroom', 'roll_no'), name='unique_roll_no_per_class'),
        ),
        migrations.AddConstraint(
            model_name='classsubjectchapter',
            constraint=models.UniqueConstraint(fields=('class_subject', 'number'), name='unique_chapter_number_per_class_subject'),
        ),
        migrations.AddConstraint(
            model_name='copycheckrecord',
            constraint=models.UniqueConstraint(fields=('student', 'chapter'), name='unique_student_chapter_record'),
        ),
    ]
