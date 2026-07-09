from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('checker', '0003_flexible_copy_checking'),
    ]

    operations = [
        migrations.AddField(
            model_name='teachercourseprogress',
            name='admin_detail',
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name='teachercourseprogress',
            name='detail',
            field=models.TextField(blank=True),
        ),
    ]
