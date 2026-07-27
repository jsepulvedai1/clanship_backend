# Generated manually for User session keys

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0020_professionalprofile_address_latitude_longitude'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='client_session_key',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Clave de Sesión Cliente Activa'),
        ),
        migrations.AddField(
            model_name='user',
            name='tradesman_session_key',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Clave de Sesión Maestro Activa'),
        ),
    ]
