"""
tests/test_batch_performance.py
Tests de rendimiento y correctitud del pipeline batch completo.

Valida:
  - Correctitud matemática de las reglas de cobertura (exactitud 100%)
  - Conciliación de integridad (recibidas == procesadas + cuarentena)
  - SLA de rendimiento (>= 139 órdenes/segundo)
  - Privacidad PII (hashes SHA-256 correctos, sin datos en claro)
  - Escritura Parquet con esquema correcto
  - Retrocompatibilidad con CSV (modo fallback)
"""

from __future__ import annotations

import csv
import glob
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, List

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SAMPLE_CSV         = PROJECT_ROOT / "dataset" / "sample_1000.csv"
CATALOGO_SERVICIOS = PROJECT_ROOT / "dataset" / "COIL_catalogo_servicios_cubiertos.csv"
CATALOGO_PERFILES  = PROJECT_ROOT / "dataset" / "COIL_catalogo_perfiles_cobertura.csv"


# ── Fixture: ejecutar batch una vez en un dir temporal ───────────────────────
@pytest.fixture(scope="module")
def batch_result_parquet():
    """Ejecuta el batch sobre sample_1000 con Parquet. Reutiliza entre tests del módulo."""
    if not SAMPLE_CSV.exists():
        pytest.skip(f"sample_1000.csv no encontrado en {SAMPLE_CSV}")

    from src.batch_processor import process_batch

    with tempfile.TemporaryDirectory(prefix="coil_perf_parq_") as tmpdir:
        metrics = process_batch(
            input_csv_path=str(SAMPLE_CSV),
            catalogo_servicios_path=str(CATALOGO_SERVICIOS),
            catalogo_perfiles_path=str(CATALOGO_PERFILES),
            output_dir=tmpdir,
            run_id="RUN-PERF-PARQUET",
            chunk_size=500,
            write_parquet=True,
        )
        yield metrics, tmpdir


@pytest.fixture(scope="module")
def batch_result_csv():
    """Ejecuta el batch sobre sample_1000 con CSV fallback."""
    if not SAMPLE_CSV.exists():
        pytest.skip(f"sample_1000.csv no encontrado en {SAMPLE_CSV}")

    from src.batch_processor import process_batch

    with tempfile.TemporaryDirectory(prefix="coil_perf_csv_") as tmpdir:
        metrics = process_batch(
            input_csv_path=str(SAMPLE_CSV),
            catalogo_servicios_path=str(CATALOGO_SERVICIOS),
            catalogo_perfiles_path=str(CATALOGO_PERFILES),
            output_dir=tmpdir,
            run_id="RUN-PERF-CSV",
            chunk_size=500,
            write_parquet=False,  # Forzar CSV
        )
        yield metrics, tmpdir


# ===========================================================================
# 1. CONCILIACIÓN DE INTEGRIDAD
# ===========================================================================

class TestIntegridad:

    def test_ecuacion_integridad_parquet(self, batch_result_parquet):
        """RF-11: recibidas == procesadas + cuarentena (Parquet)."""
        metrics, _ = batch_result_parquet
        assert metrics["conciliacion_integridad"]["estado"] == "CUADRADA_PERFECTA"
        assert metrics["conciliacion_integridad"]["diferencia"] == 0

    def test_ecuacion_integridad_csv(self, batch_result_csv):
        """RF-11: recibidas == procesadas + cuarentena (CSV)."""
        metrics, _ = batch_result_csv
        assert metrics["conciliacion_integridad"]["estado"] == "CUADRADA_PERFECTA"

    def test_total_1000_registros(self, batch_result_parquet):
        """sample_1000.csv debe tener exactamente 1000 registros."""
        metrics, _ = batch_result_parquet
        assert metrics["total_recibidas"] == 1000

    def test_cubiertas_mas_no_cubiertas_igual_procesadas(self, batch_result_parquet):
        """Cubiertas + No cubiertas == Total procesadas."""
        m = batch_result_parquet[0]
        assert m["total_cubiertas"] + m["total_no_cubiertas"] == m["total_procesadas"]

    def test_porcentaje_cubiertas_rango_valido(self, batch_result_parquet):
        """Porcentaje de cobertura entre 0 y 100."""
        m = batch_result_parquet[0]
        assert 0 <= m["porcentaje_cubiertas"] <= 100

    def test_valor_reconocido_menor_igual_solicitado(self, batch_result_parquet):
        """El valor reconocido nunca supera el solicitado."""
        m = batch_result_parquet[0]
        assert m["valor_reconocido_total_cop"] <= m["valor_solicitado_total_cop"]

    def test_valor_solicitado_positivo(self, batch_result_parquet):
        """El valor solicitado total es positivo."""
        m = batch_result_parquet[0]
        assert m["valor_solicitado_total_cop"] > 0

    def test_formato_salida_parquet(self, batch_result_parquet):
        """El campo formato_salida es 'parquet' cuando write_parquet=True."""
        m = batch_result_parquet[0]
        assert m.get("formato_salida") == "parquet"

    def test_formato_salida_csv(self, batch_result_csv):
        """El campo formato_salida es 'csv' cuando write_parquet=False."""
        m = batch_result_csv[0]
        assert m.get("formato_salida") == "csv"


# ===========================================================================
# 2. SLA DE RENDIMIENTO (RNF-01, RNF-02)
# ===========================================================================

class TestRendimiento:

    def test_cumple_sla_24h(self, batch_result_parquet):
        """RNF-01: El procesamiento de 1000 órdenes debe ser < 24 horas."""
        m, _ = batch_result_parquet
        assert m["cumple_sla_24h"] is True
        assert m["duracion_segundos"] < 86400

    def test_cumple_rendimiento_minimo(self, batch_result_parquet):
        """RNF-02: >= 139 órdenes/segundo (extrapolado de 12M en < 24h)."""
        m, _ = batch_result_parquet
        assert m["cumple_rendimiento_minimo"] is True
        assert m["rendimiento_ordenes_por_segundo"] >= 139.0

    def test_rendimiento_sample_1000_muy_rapido(self, batch_result_parquet):
        """1000 órdenes deben procesarse en < 30 segundos en cualquier hardware."""
        m, _ = batch_result_parquet
        assert m["duracion_segundos"] < 30.0, (
            f"Tardó {m['duracion_segundos']:.2f}s — revisar hardware o lógica"
        )


# ===========================================================================
# 3. ARCHIVOS DE SALIDA
# ===========================================================================

class TestArchivosParquet:

    def test_parquet_creados(self, batch_result_parquet):
        """Se generaron archivos .parquet en gold_curated/."""
        _, tmpdir = batch_result_parquet
        parquet_files = glob.glob(
            os.path.join(tmpdir, "gold_curated", "**", "*.parquet"), recursive=True
        )
        assert len(parquet_files) > 0, "No se generaron archivos Parquet"

    def test_parquet_particionado_por_fecha(self, batch_result_parquet):
        """Los Parquets están en carpetas fecha_solicitud=YYYY-MM-DD."""
        _, tmpdir = batch_result_parquet
        gold_dir = os.path.join(tmpdir, "gold_curated")
        partitions = [
            d for d in os.listdir(gold_dir)
            if os.path.isdir(os.path.join(gold_dir, d))
            and d.startswith("fecha_solicitud=")
        ]
        assert len(partitions) > 0, "No se encontraron particiones por fecha"

    def test_parquet_esquema_correcto(self, batch_result_parquet):
        """Los archivos Parquet tienen las columnas esperadas del esquema gold."""
        try:
            import pyarrow.parquet as pq
        except ImportError:
            pytest.skip("PyArrow no instalado")

        _, tmpdir = batch_result_parquet
        parquet_files = glob.glob(
            os.path.join(tmpdir, "gold_curated", "**", "*.parquet"), recursive=True
        )
        assert parquet_files, "No hay Parquets para validar"

        schema = pq.read_schema(parquet_files[0])
        schema_names = [f.name for f in schema]

        required_cols = [
            "id_solicitud", "decision", "porcentaje_cobertura",
            "valor_procedimiento", "valor_reconocido",
            "dno_hash", "seguro_social_hash", "paciente_hash",
            "id_corrida", "regla_aplicada",
        ]
        for col in required_cols:
            assert col in schema_names, f"Columna '{col}' faltante en el esquema Parquet"

    def test_parquet_leible_con_pyarrow(self, batch_result_parquet):
        """Los archivos Parquet se pueden leer con PyArrow sin errores."""
        try:
            import pyarrow.parquet as pq
        except ImportError:
            pytest.skip("PyArrow no instalado")

        _, tmpdir = batch_result_parquet
        parquet_files = glob.glob(
            os.path.join(tmpdir, "gold_curated", "**", "*.parquet"), recursive=True
        )
        assert parquet_files

        total_rows = 0
        for pf in parquet_files:
            table = pq.read_table(pf)
            total_rows += len(table)

        # Debe haber registros
        assert total_rows > 0

    def test_cuarentena_csv_creado(self, batch_result_parquet):
        """Se crea el archivo de cuarentena CSV."""
        _, tmpdir = batch_result_parquet
        q_files = glob.glob(os.path.join(tmpdir, "quarantine", "quarantine_*.csv"))
        assert len(q_files) > 0, "No se creó el archivo de cuarentena"

    def test_metrics_json_creado(self, batch_result_parquet):
        """Se crea el archivo de métricas JSON."""
        _, tmpdir = batch_result_parquet
        m_files = glob.glob(os.path.join(tmpdir, "metrics_*.json"))
        assert len(m_files) > 0, "No se creó el archivo de métricas"

    def test_metrics_json_campos_completos(self, batch_result_parquet):
        """El JSON de métricas tiene todos los campos requeridos."""
        _, tmpdir = batch_result_parquet
        m_files = glob.glob(os.path.join(tmpdir, "metrics_*.json"))
        with open(m_files[0], "r", encoding="utf-8") as f:
            data = json.load(f)

        required_fields = [
            "id_corrida", "total_recibidas", "total_procesadas",
            "total_cubiertas", "total_no_cubiertas", "total_cuarentena",
            "valor_solicitado_total_cop", "valor_reconocido_total_cop",
            "conciliacion_integridad", "cumple_sla_24h",
            "cumple_rendimiento_minimo", "formato_salida",
        ]
        for field in required_fields:
            assert field in data, f"Campo '{field}' faltante en metrics JSON"


class TestArchivosCsv:

    def test_csv_creados(self, batch_result_csv):
        """Se generaron archivos .csv en gold_curated/ con write_parquet=False."""
        _, tmpdir = batch_result_csv
        csv_files = glob.glob(
            os.path.join(tmpdir, "gold_curated", "**", "*.csv"), recursive=True
        )
        assert len(csv_files) > 0, "No se generaron archivos CSV"

    def test_csv_cabecera_correcta(self, batch_result_csv):
        """Los CSV tienen los campos gold correctos."""
        _, tmpdir = batch_result_csv
        csv_files = glob.glob(
            os.path.join(tmpdir, "gold_curated", "**", "*.csv"), recursive=True
        )
        with open(csv_files[0], "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []

        required_headers = [
            "id_solicitud", "decision", "dno_hash", "valor_reconocido"
        ]
        for h in required_headers:
            assert h in headers, f"Cabecera '{h}' faltante en CSV gold"


# ===========================================================================
# 4. PRIVACIDAD PII (RNF-09, Ley 1581)
# ===========================================================================

class TestPrivacidadPII:

    def test_hashes_sha256_longitud_64(self, batch_result_parquet):
        """Los hashes PII tienen exactamente 64 caracteres hexadecimales."""
        try:
            import pyarrow.parquet as pq
        except ImportError:
            pytest.skip("PyArrow no instalado")

        _, tmpdir = batch_result_parquet
        parquet_files = glob.glob(
            os.path.join(tmpdir, "gold_curated", "**", "*.parquet"), recursive=True
        )
        if not parquet_files:
            pytest.skip("No hay Parquets")

        table = pq.read_table(parquet_files[0])
        rows  = table.to_pylist()

        errores = 0
        for row in rows[:100]:  # Verificar primeras 100 filas
            for hash_col in ("dno_hash", "seguro_social_hash", "paciente_hash"):
                val = row.get(hash_col, "")
                if val and len(val) != 64:
                    errores += 1

        assert errores == 0, f"Se encontraron {errores} hashes con longitud incorrecta"

    def test_hashes_son_hexadecimales(self, batch_result_parquet):
        """Los hashes PII son valores hexadecimales válidos (SHA-256)."""
        try:
            import pyarrow.parquet as pq
        except ImportError:
            pytest.skip("PyArrow no instalado")

        _, tmpdir = batch_result_parquet
        parquet_files = glob.glob(
            os.path.join(tmpdir, "gold_curated", "**", "*.parquet"), recursive=True
        )
        if not parquet_files:
            pytest.skip("No hay Parquets")

        table = pq.read_table(parquet_files[0])
        rows  = table.to_pylist()

        for row in rows[:50]:
            for hash_col in ("dno_hash", "seguro_social_hash", "paciente_hash"):
                val = row.get(hash_col, "")
                if val and len(val) == 64:
                    # Verificar que es hexadecimal válido
                    try:
                        int(val, 16)
                    except ValueError:
                        pytest.fail(f"Hash inválido en {hash_col}: {val[:16]}...")

    def test_no_dno_real_en_gold(self, batch_result_parquet):
        """El DNO original no debe aparecer en la capa gold."""
        try:
            import pyarrow.parquet as pq
        except ImportError:
            pytest.skip("PyArrow no instalado")

        _, tmpdir = batch_result_parquet
        parquet_files = glob.glob(
            os.path.join(tmpdir, "gold_curated", "**", "*.parquet"), recursive=True
        )
        if not parquet_files:
            pytest.skip("No hay Parquets")

        table   = pq.read_table(parquet_files[0])
        columns = [f.name for f in table.schema]

        # Los campos PII crudos NO deben estar en la capa gold
        pii_columns_raw = {"dno", "seguro_social", "paciente"}
        found_pii = pii_columns_raw.intersection(set(columns))
        assert len(found_pii) == 0, (
            f"Datos PII en claro encontrados en capa gold: {found_pii}"
        )

    def test_hash_sha256_consistente(self):
        """El mismo valor siempre produce el mismo hash SHA-256."""
        from src.utils.glosa_parser import hash_sha256

        texto = "DNO-12345678"
        hash1 = hash_sha256(texto)
        hash2 = hash_sha256(texto)

        assert hash1 == hash2
        assert len(hash1) == 64
        # Verificar contra hashlib directamente
        esperado = hashlib.sha256(texto.encode("utf-8")).hexdigest()
        assert hash1 == esperado


# ===========================================================================
# 5. CORRECTITUD DE REGLAS DE COBERTURA
# ===========================================================================

class TestReglasCoberturaCompleto:
    """Tests de extremo a extremo de la lógica de negocio."""

    @pytest.fixture(autouse=True)
    def setup_engine(self):
        from src.utils.rule_engine import CoverageRuleEngine
        self.engine = CoverageRuleEngine(
            str(CATALOGO_SERVICIOS),
            str(CATALOGO_PERFILES),
        )

    @pytest.mark.parametrize("perfil,pct_esperado", [
        ("PRIORITARIO", 100),
        ("ESTANDAR", 50),
        ("COPAGO", 25),
    ])
    def test_porcentajes_por_perfil(self, perfil, pct_esperado):
        """Cada perfil aplica el porcentaje correcto a un servicio cubierto."""
        result = self.engine.evaluate_order(
            servicio_solicitado="Consulta de medicina general",
            perfil_cobertura=perfil,
            valor_procedimiento=100_000,
            medicaciones=[],
        )
        assert result["decision"] == "CUBRE"
        assert result["porcentaje_cobertura"] == pct_esperado
        assert result["valor_reconocido"] == int(100_000 * pct_esperado / 100)

    @pytest.mark.parametrize("valor,alerta_esperada", [
        (20_000, "VALOR_BAJO_RANGO"),    # valor_min = 35000
        (200_000, "VALOR_SOBRE_RANGO"),  # valor_max = 95000
        (60_000, "NINGUNA"),
    ])
    def test_alertas_por_valor(self, valor, alerta_esperada):
        """Las alertas de rango se generan correctamente según el valor."""
        result = self.engine.evaluate_order(
            servicio_solicitado="Consulta de medicina general",
            perfil_cobertura="PRIORITARIO",
            valor_procedimiento=valor,
            medicaciones=[],
        )
        assert alerta_esperada in result["alertas"]

    def test_servicio_no_cubierto_cero(self):
        """Servicio no en catálogo → decision NO CUBRE, reconocido = 0."""
        result = self.engine.evaluate_order(
            servicio_solicitado="Cirugía estética no autorizada",
            perfil_cobertura="PRIORITARIO",
            valor_procedimiento=500_000,
            medicaciones=[],
        )
        assert result["decision"] == "NO CUBRE"
        assert result["valor_reconocido"] == 0
        assert result["codigo_servicio"] == "NON-COVERED"
        assert "SERVICIO_FUERA_DE_CATALOGO" in result["alertas"]

    def test_medicacion_no_concuerda(self):
        """Si las medicaciones no coinciden con las de referencia, se genera alerta."""
        result = self.engine.evaluate_order(
            servicio_solicitado="Consulta de medicina general",
            perfil_cobertura="PRIORITARIO",
            valor_procedimiento=60_000,
            medicaciones=["medicamento_desconocido_xyz"],
        )
        assert result["decision"] == "CUBRE"
        assert "MEDICACION_NO_CONCUERDA" in result["alertas"]

    def test_version_catalogo_en_resultado(self):
        """La versión del catálogo aparece en cada resultado."""
        result = self.engine.evaluate_order(
            servicio_solicitado="Hemograma completo",
            perfil_cobertura="ESTANDAR",
            valor_procedimiento=50_000,
            medicaciones=[],
        )
        assert result["version_catalogo"] == "2026.1"

    def test_todos_servicios_catalogados_son_cubiertos(self):
        """Cada uno de los 20 servicios del catálogo produce CUBRE."""
        if not CATALOGO_SERVICIOS.exists():
            pytest.skip("Catálogo no encontrado")

        with open(CATALOGO_SERVICIOS, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            servicios = [row["servicio"] for row in reader]

        for servicio in servicios:
            result = self.engine.evaluate_order(
                servicio_solicitado=servicio,
                perfil_cobertura="PRIORITARIO",
                valor_procedimiento=70_000,
                medicaciones=[],
            )
            assert result["decision"] == "CUBRE", (
                f"Servicio '{servicio}' debería ser CUBRE"
            )

    def test_calculo_financiero_exacto(self):
        """La liquidación financiera es matemáticamente exacta."""
        casos = [
            (100_000, "PRIORITARIO", 100_000),
            (100_000, "ESTANDAR",    50_000),
            (100_000, "COPAGO",      25_000),
            (75_000,  "ESTANDAR",    37_500),
            (33_333,  "COPAGO",       8_333),  # int(round(33333 * 0.25))
        ]
        for valor, perfil, reconocido_esperado in casos:
            result = self.engine.evaluate_order(
                servicio_solicitado="Consulta de medicina general",
                perfil_cobertura=perfil,
                valor_procedimiento=valor,
                medicaciones=[],
            )
            assert result["valor_reconocido"] == reconocido_esperado, (
                f"valor={valor}, perfil={perfil}: "
                f"esperado={reconocido_esperado}, obtenido={result['valor_reconocido']}"
            )
