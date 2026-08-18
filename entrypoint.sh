#!/usr/bin/env bash
set -o errexit
set -o pipefail
set -o nounset

# Esperar a que la base de datos esté lista si DB_HOST está definido
if [ -n "${DB_HOST:-}" ]; then
  echo "==> Esperando a PostgreSQL en $DB_HOST:${DB_PORT:-5432}..."
  # Usar pg_isready para verificar la disponibilidad de la base de datos
  until pg_isready -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "${DB_USER:-postgres}" -t 1; do
    echo "==> PostgreSQL no está listo todavía, esperando 2 segundos..."
    sleep 2
  done
  echo "==> ¡PostgreSQL está listo!"
fi

echo "==> Aplicando migraciones (migrate)..."
python manage.py migrate --no-input

echo "==> Recopilando archivos estáticos (collectstatic)..."
python manage.py collectstatic --no-input

echo "==> Ejecutando script de creación de superusuario..."
python create_admin.py

echo "==> Iniciando Daphne (ASGI) en el puerto 8000 con ping-interval..."
exec daphne -b 0.0.0.0 -p 8000 --ping-interval 20 --ping-timeout 30 core.asgi:application
