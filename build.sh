#!/usr/bin/env bash
# Salir inmediatamente si un comando falla
set -o errexit

echo "==> Instalando dependencias..."
pip install -r requirements.txt

echo "==> Generando archivos de migraciones (makemigrations)..."
python manage.py makemigrations

echo "==> Aplicando migraciones en la base de datos (migrate)..."
python manage.py migrate

echo "==> Recopilando archivos estáticos (collectstatic)..."
python manage.py collectstatic --no-input  # <-- AGREGA ESTA LÍNEA

echo "==> Ejecutando script de superusuario..."
python create_admin.py

echo "==> ¡Proceso de Build Completado con éxito!"