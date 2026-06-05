FROM python:3.11-slim

# Evitar que Python escriba archivos .pyc en el disco
ENV PYTHONDONTWRITEBYTECODE 1
# Evitar que Python almacene en búfer stdout y stderr
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# Instalar dependencias del sistema necesarias para PostGIS, GDAL y compilación de paquetes
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    binutils \
    libproj-dev \
    gdal-bin \
    postgresql-client \
    mime-support \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias de Python
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código del proyecto
COPY . /app/

# Dar permisos de ejecución al script de entrada
RUN chmod +x /app/entrypoint.sh

# Exponer el puerto en el que correrá Daphne (ASGI)
EXPOSE 8000

# Definir el script de entrada
ENTRYPOINT ["/app/entrypoint.sh"]
