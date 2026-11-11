from django.db import migrations


def update_professional_welcome_template(apps, schema_editor):
    WelcomeEmailTemplate = apps.get_model('users', 'WelcomeEmailTemplate')
    from users.models import WelcomeEmailTemplate as ModelClass

    defaults = ModelClass.get_default_data('PROFESSIONAL')
    obj, created = WelcomeEmailTemplate.objects.get_or_create(
        user_type='PROFESSIONAL',
        defaults=defaults,
    )
    if not created:
        for field, value in defaults.items():
            if field == 'is_active':
                continue
            setattr(obj, field, value)
        obj.save()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0057_welcome_email_template'),
    ]

    operations = [
        migrations.RunPython(update_professional_welcome_template, noop_reverse),
    ]
