# create_admin.py
import os
import django

# Configuramos el entorno de Django antes de importar los modelos
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth import get_user_model

def generate_superuser():
    User = get_user_model()
    
    # Buscamos las credenciales desde variables de entorno. 
    # Si no existen en Render, usará por defecto 'admin' y 'admin' como pediste.
    username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
    email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@clanship.cl')
    password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'Clanship2026!')

    user, created = User.objects.get_or_create(username=username, defaults={'email': email})
    user.email = email
    user.set_password(password)
    user.is_staff = True
    user.is_superuser = True
    if hasattr(user, 'user_type'):
        user.user_type = 'ADMIN'
    user.save()
    if created:
        print(f"==> ¡Superusuario '{username}' creado con éxito! 🎉")
    else:
        print(f"==> Superusuario '{username}' actualizado con contraseña y permisos de administrador. ✅")

if __name__ == '__main__':
    generate_superuser()