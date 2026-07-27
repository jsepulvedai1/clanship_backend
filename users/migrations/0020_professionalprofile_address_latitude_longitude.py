# Generated manually for ProfessionalProfile location fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0019_systemsetting'),
    ]

    operations = [
        migrations.AddField(
            model_name='professionalprofile',
            name='address',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Dirección Profesional / Taller'),
        ),
        migrations.AddField(
            model_name='professionalprofile',
            name='latitude',
            field=models.DecimalField(blank=True, decimal_places=9, max_digits=12, null=True, verbose_name='Latitud Profesional'),
        ),
        migrations.AddField(
            model_name='professionalprofile',
            name='longitude',
            field=models.DecimalField(blank=True, decimal_places=9, max_digits=12, null=True, verbose_name='Longitud Profesional'),
        ),
    ]
