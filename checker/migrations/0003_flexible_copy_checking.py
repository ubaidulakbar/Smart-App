from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('checker', '0002_teacher_module'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='copycheckrecord',
            name='unique_student_chapter_record',
        ),
        migrations.AlterField(
            model_name='copycheckrecord',
            name='chapter',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='copy_records', to='checker.classsubjectchapter'),
        ),
        migrations.AlterField(
            model_name='copycheckrecord',
            name='status',
            field=models.CharField(choices=[('complete', 'Complete'), ('incomplete', 'Incomplete')], default='complete', max_length=30),
        ),
    ]
