# Generated manually to align DB schema with current Profiles model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_alter_crew_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='profiles',
            name='gender',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AlterField(
            model_name='profiles',
            name='dateOfBirth',
            field=models.DateField(blank=True, null=True),
        ),
    ]
