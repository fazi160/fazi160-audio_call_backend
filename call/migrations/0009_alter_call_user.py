# Generated manually to make user field optional

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('call', '0008_call_call_direction'),
    ]

    operations = [
        migrations.AlterField(
            model_name='call',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='auth.user'),
        ),
    ] 