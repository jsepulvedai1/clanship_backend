# Generated to normalize existing users' names to Title Case (Nombre Apellido)

from django.db import migrations

def normalize_names_to_title_case(apps, schema_editor):
    User = apps.get_model('users', 'User')
    for user in User.objects.all():
        updated_fields = []
        if user.first_name:
            title_first = user.first_name.strip().title()
            if title_first != user.first_name:
                user.first_name = title_first
                updated_fields.append('first_name')
        if user.last_name:
            title_last = user.last_name.strip().title()
            if title_last != user.last_name:
                user.last_name = title_last
                updated_fields.append('last_name')
        if updated_fields:
            user.save(update_fields=updated_fields)

class Migration(migrations.Migration):

    dependencies = [
        ('users', '0033_user_blocked_users_userreport'),
    ]

    operations = [
        migrations.RunPython(normalize_names_to_title_case, reverse_code=migrations.RunPython.noop),
    ]
