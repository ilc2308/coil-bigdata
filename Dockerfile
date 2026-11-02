# ============================================================
# COIL Big Data — Dockerfile de la API FastAPI
# Imagen base: Python 3.11-slim (Debian Bookworm)
# ============================================================

# ---- Stage 1: Builder — instala dependencias ----
FROM python:3.11-slim AS builder

WORKDIR /build

# Copiar solo requirements para maximizar cache de capas Docker
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt


# ---- Stage 2: Runtime — imagen final mínima ----
FROM python:3.11-slim AS runtime

# Buenas prácticas Python en Docker
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Copiar dependencias compiladas desde el builder
COPY --from=builder /install /usr/local

# Copiar código fuente
COPY src/  ./src/
COPY api/  ./api/

# Solo catálogos y muestra en la imagen (el dataset grande va en volumen)
COPY dataset/COIL_catalogo_servicios_cubiertos.csv ./dataset/
COPY dataset/COIL_catalogo_perfiles_cobertura.csv  ./dataset/
COPY dataset/sample_1000.csv                        ./dataset/

# Crear directorios de trabajo
RUN mkdir -p /app/output/gold_curated \
             /app/output/quarantine \
             /app/uploads

# Usuario no-root para seguridad (principio de menor privilegio)
RUN useradd -m -u 1000 coiluser \
    && chown -R coiluser:coiluser /app
USER coiluser

# Puerto de la API
EXPOSE 8000

# Healthcheck para docker-compose depends_on
HEALTHCHECK --interval=20s --timeout=8s --start-period=20s --retries=4 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Arrancar uvicorn en modo producción (sin --reload)
CMD ["uvicorn", "api.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--log-level", "info"]
