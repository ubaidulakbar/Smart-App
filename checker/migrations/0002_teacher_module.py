# Generated for Smart Copy Checking teacher-progress module.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('checker', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='role',
            field=models.CharField(choices=[('admin', 'Admin'), ('checker', 'Checker'), ('teacher', 'Teacher')], default='checker', max_length=20),
        ),
        migrations.AddField(
            model_name='correctionrequest',
            name='requested_actual_checker_name',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.CreateModel(
            name='TeacherCourseAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('class_subject', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='teacher_assignments', to='checker.classsubject')),
                ('teacher', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='teacher_course_assignments', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['class_subject__classroom__name', 'class_subject__classroom__section', 'class_subject__subject__name'],
            },
        ),
        migrations.CreateModel(
            name='TeacherCourseProgress',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('week_no', models.PositiveIntegerField()),
                ('detail', models.TextField()),
                ('status', models.CharField(choices=[('not_completed', 'Not Completed'), ('completed', 'Completed')], default='not_completed', max_length=30)),
                ('locked', models.BooleanField(default=False)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('assignment', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='progress_rows', to='checker.teachercourseassignment')),
            ],
            options={
                'ordering': ['assignment__class_subject__classroom__name', 'assignment__class_subject__classroom__section', 'assignment__class_subject__subject__name', 'week_no'],
            },
        ),
        migrations.CreateModel(
            name='TeacherProgressCorrectionRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.TextField()),
                ('requested_detail', models.TextField()),
                ('requested_status', models.CharField(choices=[('not_completed', 'Not Completed'), ('completed', 'Completed')], default='not_completed', max_length=30)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending', max_length=20)),
                ('admin_note', models.TextField(blank=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('progress', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='correction_requests', to='checker.teachercourseprogress')),
                ('requested_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='teacher_progress_correction_requests', to=settings.AUTH_USER_MODEL)),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='reviewed_teacher_progress_requests', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='teachercourseassignment',
            constraint=models.UniqueConstraint(condition=models.Q(is_active=True), fields=('class_subject',), name='unique_active_teacher_per_class_subject'),
        ),
        migrations.AddConstraint(
            model_name='teachercourseprogress',
            constraint=models.UniqueConstraint(fields=('assignment', 'week_no'), name='unique_week_no_per_teacher_course'),
        ),
    ]
