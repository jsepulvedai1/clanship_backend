from django.db import migrations


def fix_professional_user_type(apps, schema_editor):
    User = apps.get_model('users', 'User')
    User.objects.filter(
        user_type='CUSTOMER',
        professional_profile__isnull=False,
    ).update(user_type='PROFESSIONAL')


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0058_update_professional_welcome_email'),
    ]

    operations = [
        migrations.RunPython(fix_professional_user_type, noop_reverse),
    ]
