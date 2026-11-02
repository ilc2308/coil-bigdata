#!/bin/bash
# ============================================================
# COIL Big Data — Script de Despliegue en EC2 (Ubuntu 22.04)
#
# Uso:
#   chmod +x infrastructure/deploy_ec2.sh
#   ./infrastructure/deploy_ec2.sh
#
# Pre-requisitos en la instancia EC2:
#   - Ubuntu 22.04 LTS (t3.medium o superior recomendado)
#   - Puerto 80 abierto en el Security Group
#   - Clave SSH configurada
#
# ¡IMPORTANTE!
# - Solo despliega si tienes autorización explícita del equipo
# - No genera costos de AWS si usas el servidor web de EC2 local
# ============================================================

set -e  # Salir ante cualquier error

echo "============================================================"
echo " COIL Big Data — Despliegue en EC2 (Ubuntu 22.04)"
echo "============================================================"

# ── 1. Actualizar sistema ────────────────────────────────────
echo "[1/7] Actualizando sistema..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git

# ── 2. Instalar Docker ───────────────────────────────────────
echo "[2/7] Instalando Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker "$USER"
    echo "  Docker instalado. Puede requerir re-login."
else
    echo "  Docker ya instalado: $(docker --version)"
fi

# ── 3. Instalar Docker Compose ───────────────────────────────
echo "[3/7] Instalando Docker Compose..."
if ! command -v docker compose &> /dev/null; then
    sudo apt-get install -y docker-compose-plugin
fi
echo "  Docker Compose: $(docker compose version)"

# ── 4. Clonar o actualizar repositorio ──────────────────────
echo "[4/7] Preparando código fuente..."
REPO_DIR="$HOME/proyecto-coil-bigdata"

if [ -d "$REPO_DIR" ]; then
    echo "  Repositorio ya existe — actualizando..."
    cd "$REPO_DIR"
    git pull origin main
else
    echo "  Clonando repositorio..."
    # Reemplaza con la URL real de tu repositorio
    git clone https://github.com/ilc2308/coil-bigdata.git "$REPO_DIR"
    cd "$REPO_DIR"
fi

# ── 5. Configurar variables de entorno ──────────────────────
echo "[5/7] Configurando .env..."
if [ ! -f .env ]; then
    cp .env.example .env
    if command -v openssl &> /dev/null; then
        RANDOM_KEY=$(openssl rand -hex 24)
        sed -i "s/cambia_esta_clave_secreta_en_produccion/$RANDOM_KEY/" .env 2>/dev/null || true
    fi
    echo "  ⚠️  .env generado desde .env.example."
    if [ "$1" != "-y" ] && [ -t 0 ]; then
        echo "  Credenciales por defecto: admin / coil2026"
        read -p "  ¿Deseas continuar con estas credenciales? [S/n]: " confirm
        if [[ "$confirm" =~ ^[nN]$ ]]; then
            echo "  Edita .env y vuelve a ejecutar el script."
            exit 1
        fi
    fi
fi

# ── 6. Crear directorios necesarios ─────────────────────────
echo "[6/7] Creando directorios de datos..."
mkdir -p uploads output/gold_curated output/quarantine

# ── 7. Construir e iniciar servicios ────────────────────────
echo "[7/7] Construyendo e iniciando servicios..."
sudo docker compose -f docker-compose.prod.yml build --no-cache
sudo docker compose -f docker-compose.prod.yml up -d

# ── Verificar estado ─────────────────────────────────────────
echo ""
echo "Esperando que los servicios inicien (30s)..."
sleep 30

echo ""
echo "Estado de los contenedores:"
sudo docker compose -f docker-compose.prod.yml ps

echo ""
PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo "<IP-del-servidor>")
echo "============================================================"
echo " COIL desplegado exitosamente!"
echo ""
echo "   Dashboard: http://$PUBLIC_IP"
echo "   API REST:  http://$PUBLIC_IP/api/v1"
echo "   Swagger:   http://$PUBLIC_IP/docs"
echo ""
echo "   Login: usuario y contraseña definidos en .env"
echo "============================================================"
