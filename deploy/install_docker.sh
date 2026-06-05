#!/usr/bin/env bash
# Script para instalar Docker y Docker Compose en servidores Ubuntu limpios.
# Salir si ocurre cualquier error
set -o errexit
set -o pipefail

echo "==> Iniciando la instalación de Docker..."

# 1. Actualizar el índice de paquetes del sistema
echo "==> Actualizando paquetes del sistema..."
sudo apt-get update -y
sudo apt-get upgrade -y

# 2. Instalar dependencias previas
echo "==> Instalando dependencias de transporte HTTPS..."
sudo apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# 3. Crear directorio para las llaves de Docker y añadir su llave GPG oficial
echo "==> Añadiendo la llave GPG oficial de Docker..."
sudo mkdir -p /etc/apt/keyrings
if [ -f /etc/apt/keyrings/docker.gpg ]; then
    sudo rm /etc/apt/keyrings/docker.gpg
fi
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# 4. Configurar el repositorio oficial estable de Docker
echo "==> Configurando el repositorio de Docker..."
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 5. Instalar Docker Engine, CLI y el Plugin de Docker Compose
echo "==> Instalando Docker y Docker Compose..."
sudo apt-get update -y
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 6. Iniciar y habilitar el servicio de Docker
echo "==> Habilitando e iniciando el servicio de Docker..."
sudo systemctl enable docker
sudo systemctl start docker

# 7. Verificar instalación
echo "==> Verificando versiones instaladas..."
docker --version
docker compose version

echo "==> ¡Docker y Docker Compose se han instalado correctamente! 🎉"
echo "==> Puedes ejecutar comandos usando 'sudo docker' o configurar tu usuario en el grupo docker:"
echo "    sudo usermod -aG docker \$USER"
echo "    (Nota: Si aplicas el grupo docker, debes cerrar sesión y volver a entrar para que tenga efecto)"
