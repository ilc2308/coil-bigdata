# ============================================================
# COIL Big Data — Makefile
# Comandos de conveniencia para desarrollo y operación
# ============================================================

.DEFAULT_GOAL := help
PYTHON        := python
PIP           := pip

.PHONY: help setup env build up down logs test test-unit test-api \
        process-sample process-full oracle clean

help: ## Mostrar esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Configuración inicial ────────────────────────────────────
setup: env install ## Configuración completa (primera vez)

env: ## Crear .env desde .env.example
	@test -f .env || (cp .env.example .env && echo ".env creado")

install: ## Instalar dependencias Python
	$(PIP) install -r requirements.txt

# ── Docker ───────────────────────────────────────────────────
build: ## Construir imágenes Docker
	docker-compose build

up: ## Iniciar todos los servicios (API + Web)
	docker-compose up -d
	@echo "API:       http://localhost:8000"
	@echo "Swagger:   http://localhost:8000/docs"
	@echo "Dashboard: http://localhost:8501"

down: ## Detener todos los servicios
	docker-compose down

logs: ## Ver logs en tiempo real
	docker-compose logs -f

# ── Tests ────────────────────────────────────────────────────
test: ## Ejecutar todos los tests
	$(PYTHON) -m pytest tests/ -v --tb=short

test-unit: ## Solo tests unitarios (sin API)
	$(PYTHON) -m pytest tests/test_components.py -v

test-api: ## Solo tests de integración de la API
	$(PYTHON) -m pytest tests/test_api_integration.py -v --tb=short

test-aws: ## Solo tests AWS (requiere moto instalado)
	$(PYTHON) -m pytest tests/test_aws_mock.py -v --tb=short

# ── Procesamiento ────────────────────────────────────────────
process-sample: ## Procesar sample_1000.csv
	$(PYTHON) -m src.batch_processor

process-full: ## Procesar dataset completo de 1.2M
	$(PYTHON) -m src.batch_processor dataset/COIL_dataset_glosas_salud_1_2M.csv

oracle: ## Ejecutar oráculo de validación sobre sample_1000
	$(PYTHON) -m src.oracle_validator

# ── API local ────────────────────────────────────────────────
api: ## Iniciar API en modo desarrollo
	uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

web: ## Iniciar Streamlit
	streamlit run app/main.py --server.port 8501

# ── Limpieza ─────────────────────────────────────────────────
clean: ## Limpiar archivos temporales
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache
