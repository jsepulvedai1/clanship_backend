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
    email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@clanship.com')
    password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin')

    if not User.objects.filter(username=username).exists():
        print(f"==> Creando superusuario de forma automática ({username})...")
        User.objects.create_superuser(username=username, email=email, password=password)
        print("==> ¡Superusuario creado con éxito! 🎉")
    else:
        print(f"==> El superusuario '{username}' ya existe. Saltando paso.")

if __name__ == '__main__':
    generate_superuser()