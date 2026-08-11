from django.db import migrations

def migrate_legacy_specialties(apps, schema_editor):
    ProfessionalProfile = apps.get_model('users', 'ProfessionalProfile')
    for profile in ProfessionalProfile.objects.filter(specialty__isnull=False):
        if not profile.specialties.exists():
            profile.specialties.add(profile.specialty)

def reverse_migration(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('users', '0026_alter_subscriptionplan_options_and_more'),
    ]

    operations = [
        migrations.RunPython(migrate_legacy_specialties, reverse_code=reverse_migration),
    ]
