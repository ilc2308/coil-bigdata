"""
tests/test_api_integration.py
Tests de integración para la API FastAPI de COIL.

Valida:
- Autenticación (login / token inválido / logout)
- Endpoints de cobertura (catálogos y evaluador)
- Pipeline completo: upload → process → results → quarantine
- Endpoints de auditoría y parseo de glosa
- Exportación de reportes (CSV)
- Health check y config
"""

from __future__ import annotations

import pytest
import pytest_asyncio


# ═══════════════════════════════════════════════════════════════════════════════
# 1. SISTEMA Y HEALTH
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_health_check(client):
    """El endpoint /health responde 200 y retorna status=healthy."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "mode" in data
    assert "version_catalogo" in data


@pytest.mark.asyncio
async def test_root_redirect(client):
    """El endpoint raíz / retorna info de la app."""
    resp = await client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["app"] == "COIL API"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. AUTENTICACIÓN
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_login_success(client, test_settings):
    """Login correcto retorna un JWT."""
    resp = await client.post(
        "/api/v1/auth/token",
        data={"username": test_settings.app_username,
              "password": test_settings.app_password},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


@pytest.mark.asyncio
async def test_login_wrong_password(client, test_settings):
    """Login con contraseña incorrecta retorna 401."""
    resp = await client.post(
        "/api/v1/auth/token",
        data={"username": test_settings.app_username, "password": "wrongpass"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_without_token(client):
    """Endpoint protegido sin token retorna 401."""
    resp = await client.get("/api/v1/results")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_invalid_token(client):
    """Endpoint protegido con token inválido retorna 401."""
    resp = await client.get(
        "/api/v1/results",
        headers={"Authorization": "Bearer token_invalido"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_auth_me(client, auth_headers):
    """GET /auth/me retorna el username del token."""
    resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert "username" in resp.json()


# ═══════════════════════════════════════════════════════════════════════════════
# 3. CATÁLOGOS DE COBERTURA
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_servicios(client, auth_headers):
    """El catálogo de servicios retorna exactamente 20 servicios."""
    resp = await client.get("/api/v1/coverage/servicios", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 20
    servicios = data["servicios"]
    assert len(servicios) == 20
    # Verificar campos obligatorios
    for s in servicios:
        assert "codigo_servicio" in s
        assert "servicio" in s
        assert "categoria" in s


@pytest.mark.asyncio
async def test_get_perfiles(client, auth_headers):
    """El catálogo de perfiles retorna los 3 perfiles con porcentajes correctos."""
    resp = await client.get("/api/v1/coverage/perfiles", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3

    perfiles_dict = {
        p["perfil_cobertura"]: int(p["porcentaje_cobertura_si_el_servicio_esta_cubierto"])
        for p in data["perfiles"]
    }
    assert perfiles_dict["PRIORITARIO"] == 100
    assert perfiles_dict["ESTANDAR"] == 50
    assert perfiles_dict["COPAGO"] == 25


# ═══════════════════════════════════════════════════════════════════════════════
# 4. EVALUADOR DE ÓRDENES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_evaluate_covered_prioritario(client, auth_headers):
    """PRIORITARIO + servicio cubierto → CUBRE 100%, valor_reconocido = valor_solicitado."""
    resp = await client.post(
        "/api/v1/coverage/evaluate",
        headers=auth_headers,
        json={
            "servicio_solicitado": "Consulta de medicina general",
            "perfil_cobertura": "PRIORITARIO",
            "valor_procedimiento": 60000,
            "medicaciones": ["acetaminofén"],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "CUBRE"
    assert data["porcentaje_cobertura"] == 100
    assert data["valor_reconocido"] == 60000
    assert data["codigo_servicio"] == "COV-001"


@pytest.mark.asyncio
async def test_evaluate_covered_estandar(client, auth_headers):
    """ESTANDAR + servicio cubierto → CUBRE 50%."""
    resp = await client.post(
        "/api/v1/coverage/evaluate",
        headers=auth_headers,
        json={
            "servicio_solicitado": "Consulta de medicina general",
            "perfil_cobertura": "ESTANDAR",
            "valor_procedimiento": 60000,
            "medicaciones": [],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "CUBRE"
    assert data["porcentaje_cobertura"] == 50
    assert data["valor_reconocido"] == 30000


@pytest.mark.asyncio
async def test_evaluate_covered_copago(client, auth_headers):
    """COPAGO + servicio cubierto → CUBRE 25%."""
    resp = await client.post(
        "/api/v1/coverage/evaluate",
        headers=auth_headers,
        json={
            "servicio_solicitado": "Consulta de medicina general",
            "perfil_cobertura": "COPAGO",
            "valor_procedimiento": 60000,
            "medicaciones": [],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["porcentaje_cobertura"] == 25
    assert resp.json()["valor_reconocido"] == 15000


@pytest.mark.asyncio
async def test_evaluate_not_covered(client, auth_headers):
    """Servicio fuera de catálogo → NO CUBRE, valor_reconocido = 0."""
    resp = await client.post(
        "/api/v1/coverage/evaluate",
        headers=auth_headers,
        json={
            "servicio_solicitado": "Cirugía estética no autorizada",
            "perfil_cobertura": "PRIORITARIO",
            "valor_procedimiento": 1000000,
            "medicaciones": [],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "NO CUBRE"
    assert data["porcentaje_cobertura"] == 0
    assert data["valor_reconocido"] == 0
    assert data["codigo_servicio"] == "NON-COVERED"
    assert "SERVICIO_FUERA_DE_CATALOGO" in data["alertas"]


@pytest.mark.asyncio
async def test_evaluate_valor_invalido(client, auth_headers):
    """valor_procedimiento <= 0 debe ser rechazado por Pydantic."""
    resp = await client.post(
        "/api/v1/coverage/evaluate",
        headers=auth_headers,
        json={
            "servicio_solicitado": "Consulta de medicina general",
            "perfil_cobertura": "PRIORITARIO",
            "valor_procedimiento": -500,
            "medicaciones": [],
        },
    )
    assert resp.status_code == 422  # Unprocessable Entity


# ═══════════════════════════════════════════════════════════════════════════════
# 5. RESULTADOS (sin procesamiento — capa gold vacía)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_results_empty(client, auth_headers):
    """GET /results retorna paginación válida aunque no haya datos."""
    resp = await client.get("/api/v1/results", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert "data" in data
    assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_results_pagination_params(client, auth_headers):
    """Los parámetros de paginación se respetan."""
    resp = await client.get(
        "/api/v1/results",
        headers=auth_headers,
        params={"page": 1, "page_size": 10},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["page"] == 1
    assert data["page_size"] == 10


@pytest.mark.asyncio
async def test_results_summary_empty(client, auth_headers):
    """GET /results/summary retorna estructura válida aunque no haya datos."""
    resp = await client.get("/api/v1/results/summary", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_ordenes" in data
    assert "porcentaje_cubiertas" in data


# ═══════════════════════════════════════════════════════════════════════════════
# 6. PIPELINE COMPLETO: batch → resultados (requiere sample_1000.csv)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_batch_metrics_integrity(sample_run_metrics):
    """
    El batch procesó sample_1000 con conciliación perfecta.
    Recibidas == Procesadas + Cuarentena.
    """
    m = sample_run_metrics
    assert m["conciliacion_integridad"]["estado"] == "CUADRADA_PERFECTA"
    assert m["conciliacion_integridad"]["diferencia"] == 0
    assert m["total_recibidas"] == 1000
    assert m["total_recibidas"] == m["total_procesadas"] + m["total_cuarentena"]


@pytest.mark.asyncio
async def test_batch_metrics_performance(sample_run_metrics):
    """El rendimiento supera el mínimo de 139 órdenes/segundo."""
    m = sample_run_metrics
    assert m["cumple_rendimiento_minimo"] is True
    assert m["rendimiento_ordenes_por_segundo"] >= 139.0


@pytest.mark.asyncio
async def test_batch_metrics_sla(sample_run_metrics):
    """El procesamiento de 1000 órdenes cumple el SLA de 24 horas."""
    assert sample_run_metrics["cumple_sla_24h"] is True


@pytest.mark.asyncio
async def test_batch_coverage_distribution(sample_run_metrics):
    """El batch produjo órdenes tanto CUBRE como NO CUBRE."""
    m = sample_run_metrics
    assert m["total_cubiertas"] > 0
    assert m["total_no_cubiertas"] > 0
    assert m["porcentaje_cubiertas"] > 0
    assert m["porcentaje_cubiertas"] <= 100


@pytest.mark.asyncio
async def test_batch_financial_values(sample_run_metrics):
    """Los valores financieros son coherentes."""
    m = sample_run_metrics
    assert m["valor_solicitado_total_cop"] > 0
    assert m["valor_reconocido_total_cop"] >= 0
    # El valor reconocido nunca puede superar el solicitado
    assert m["valor_reconocido_total_cop"] <= m["valor_solicitado_total_cop"]


@pytest.mark.asyncio
async def test_results_after_batch(client, auth_headers, sample_run_metrics, test_settings):
    """
    Después del batch, GET /results retorna datos.
    Verifica que los archivos de salida fueron creados.
    """
    import glob
    import os

    output_dir = test_settings.output_dir
    parquet_files = glob.glob(
        os.path.join(output_dir, "gold_curated", "**", "*.parquet"), recursive=True
    )
    csv_files = glob.glob(
        os.path.join(output_dir, "gold_curated", "**", "*.csv"), recursive=True
    )
    # Al menos un archivo de salida (Parquet o CSV)
    assert len(parquet_files) + len(csv_files) > 0, "No se generaron archivos en gold_curated/"


@pytest.mark.asyncio
async def test_quarantine_after_batch(sample_run_metrics):
    """La cuarentena del batch tiene 0 rechazos (muestra perfecta)."""
    assert sample_run_metrics["total_cuarentena"] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 7. AUDITORÍA — PARSEO DE GLOSA
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_parse_glosa_valid(client, auth_headers):
    """Una glosa bien formada retorna es_valido=True con todos los campos."""
    glosa = (
        "Paciente: Carlos Slim; DNO: DNO-99999999; "
        "SeguroSocial: SS-111-22-3333; Edad: 45; "
        "PerfilCobertura: PRIORITARIO; "
        "ServicioSolicitado: Consulta de medicina general; "
        "Medicacion: acetaminofén|ibuprofeno"
    )
    resp = await client.post(
        "/api/v1/audit/parse",
        headers=auth_headers,
        json={"glosa": glosa},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["es_valido"] is True
    assert data["perfil_cobertura"] == "PRIORITARIO"
    assert data["servicio_solicitado"] == "Consulta de medicina general"
    assert data["edad"] == 45
    assert len(data["medicaciones"]) == 2
    # Hash SHA-256 debe tener 64 caracteres
    assert len(data["dno_hash"]) == 64


@pytest.mark.asyncio
async def test_parse_glosa_invalid_missing_field(client, auth_headers):
    """Una glosa sin DNO retorna es_valido=False con un error descriptivo."""
    glosa = "Paciente: Solo Nombre; ServicioSolicitado: Algo; Medicacion: nada"
    resp = await client.post(
        "/api/v1/audit/parse",
        headers=auth_headers,
        json={"glosa": glosa},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["es_valido"] is False
    assert "error" in data
    assert len(data["error"]) > 0


@pytest.mark.asyncio
async def test_parse_glosa_empty(client, auth_headers):
    """Una glosa vacía retorna es_valido=False."""
    resp = await client.post(
        "/api/v1/audit/parse",
        headers=auth_headers,
        json={"glosa": ""},
    )
    assert resp.status_code == 200
    assert resp.json()["es_valido"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# 8. MÉTRICAS
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_metrics_list(client, auth_headers):
    """GET /metrics retorna una lista de corridas."""
    resp = await client.get("/api/v1/metrics", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "runs" in data
    assert isinstance(data["runs"], list)


@pytest.mark.asyncio
async def test_metrics_not_found(client, auth_headers):
    """GET /metrics/RUN-INEXISTENTE retorna 404."""
    resp = await client.get("/api/v1/metrics/RUN-INEXISTENTE-999", headers=auth_headers)
    assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# 9. CUARENTENA
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_quarantine_endpoint(client, auth_headers):
    """GET /quarantine retorna estructura paginada válida."""
    resp = await client.get("/api/v1/quarantine", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "data" in data
    assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_quarantine_summary(client, auth_headers):
    """GET /quarantine/summary retorna resumen válido."""
    resp = await client.get("/api/v1/quarantine/summary", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "por_motivo" in data


# ═══════════════════════════════════════════════════════════════════════════════
# 10. REPORTES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_report_metrics_csv(client, auth_headers):
    """GET /reports/metrics/csv retorna bytes con content-type CSV."""
    resp = await client.get("/api/v1/reports/metrics/csv", headers=auth_headers)
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")
    assert len(resp.content) > 0


@pytest.mark.asyncio
async def test_report_quarantine_csv(client, auth_headers):
    """GET /reports/quarantine/csv retorna bytes con content-type CSV."""
    resp = await client.get("/api/v1/reports/quarantine/csv", headers=auth_headers)
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")


# ═══════════════════════════════════════════════════════════════════════════════
# 11. CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_config_endpoint(client, auth_headers):
    """GET /api/v1/config retorna la configuración activa sin credenciales."""
    resp = await client.get("/api/v1/config", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "app_mode" in data
    assert "version_catalogo" in data
    # Verificar que no se exponen secretos
    assert "jwt_secret_key" not in data
    assert "app_password" not in data
    assert "aws_access_key_id" not in data
