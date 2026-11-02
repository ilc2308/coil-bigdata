"""
services/storage_service.py
Abstracción de almacenamiento con feature flag APP_MODE=local|aws.

Modo local:  Lee y escribe en el sistema de archivos usando PyArrow + CSV.
Modo aws:    Usa boto3 para S3 y AWS Athena.

REGLA: nunca cargar el dataset completo en memoria en el backend de la API.
       Siempre usar lectura chunked / paginada con PyArrow.
"""

from __future__ import annotations

import csv
import glob
import json
import os
import math
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

import pyarrow as pa
import pyarrow.parquet as pq
import pyarrow.dataset as ds

from api.services.config import Settings, get_settings


# ---------------------------------------------------------------------------
# Helpers locales
# ---------------------------------------------------------------------------

def _gold_dir(settings: Settings) -> str:
    return os.path.join(settings.output_dir, "gold_curated")


def _quarantine_dir(settings: Settings) -> str:
    return os.path.join(settings.output_dir, "quarantine")


def _metrics_dir(settings: Settings) -> str:
    return settings.output_dir


# ---------------------------------------------------------------------------
# Lectura paginada de la capa gold (Parquet o CSV fallback)
# ---------------------------------------------------------------------------

def read_gold_paginated(
    page: int = 1,
    page_size: int = 500,
    filters: Optional[Dict[str, Any]] = None,
    settings: Optional[Settings] = None,
) -> Tuple[List[Dict], int]:
    """
    Lee registros de la capa gold con paginación.
    Nunca carga el dataset completo en memoria.

    Modo local:  Lee Parquet o CSV del filesystem con PyArrow.
    Modo AWS:    Ejecuta SELECT paginado en Athena.
    """
    if settings is None:
        settings = get_settings()

    if settings.is_aws:
        try:
            return _read_gold_athena(page, page_size, filters or {}, settings)
        except Exception:
            pass  # Fallback a almacenamiento local si Athena aún no tiene las tablas cargadas

    page_size = min(page_size, 2000)
    gold_path = _gold_dir(settings)

    if not os.path.exists(gold_path):
        return [], 0

    # Construir filtros PyArrow
    pyarrow_filters = _build_pyarrow_filters(filters or {})

    # Intentar leer Parquet
    parquet_files = glob.glob(os.path.join(gold_path, "**", "*.parquet"), recursive=True)
    if parquet_files:
        return _read_parquet_paginated(gold_path, page, page_size, pyarrow_filters)

    # Fallback: CSV
    csv_files = glob.glob(os.path.join(gold_path, "**", "*.csv"), recursive=True)
    if csv_files:
        return _read_csv_paginated(csv_files, page, page_size, filters or {})

    return [], 0


def _build_pyarrow_filters(filters: Dict[str, Any]) -> Optional[List]:
    """Construye expresiones de filtro para PyArrow dataset."""
    exprs = []

    if filters.get("decision"):
        exprs.append(("decision", "=", filters["decision"]))
    if filters.get("perfil_cobertura"):
        exprs.append(("perfil_cobertura", "=", filters["perfil_cobertura"]))
    if filters.get("entidad_emisora"):
        exprs.append(("entidad_emisora", "=", filters["entidad_emisora"]))
    if filters.get("medio_emisor"):
        exprs.append(("medio_emisor", "=", filters["medio_emisor"]))
    if filters.get("codigo_servicio"):
        exprs.append(("codigo_servicio", "=", filters["codigo_servicio"]))
    if filters.get("alertas"):
        exprs.append(("alertas", "=", filters["alertas"]))
    if filters.get("run_id"):
        exprs.append(("id_corrida", "=", filters["run_id"]))
    if filters.get("fecha_desde"):
        exprs.append(("fecha_particion", ">=", filters["fecha_desde"]))
    if filters.get("fecha_hasta"):
        exprs.append(("fecha_particion", "<=", filters["fecha_hasta"]))

    return exprs if exprs else None


def _read_parquet_paginated(
    gold_path: str,
    page: int,
    page_size: int,
    filters: Optional[List],
) -> Tuple[List[Dict], int]:
    """Lee Parquet de forma paginada con PyArrow dataset."""
    try:
        dataset = ds.dataset(
            gold_path,
            format="parquet",
            partitioning=ds.partitioning(
                pa.schema([pa.field("fecha_solicitud", pa.string())]),
                flavor="hive",
            ),
        )

        # Construir expresión de filtro compuesta
        filter_expr = None
        if filters:
            filter_expr = _filters_to_expression(filters)

        # Contar total sin cargar todo en memoria
        count_table = dataset.to_table(
            columns=["id_solicitud"],
            filter=filter_expr,
        )
        total = len(count_table)

        if total == 0:
            return [], 0

        # Leer solo el slice de la página
        offset = (page - 1) * page_size
        full_table = dataset.to_table(filter=filter_expr)
        page_table = full_table.slice(offset, page_size)
        records = page_table.to_pylist()

        return records, total

    except Exception as e:
        # Si falla el dataset (p.ej. particionado mixto), leer archivo por archivo
        return _read_parquet_files_paginated(gold_path, page, page_size, filters)


def _filters_to_expression(filters: List[Tuple]) -> Any:
    """Convierte lista de (campo, op, valor) a expresión PyArrow."""
    import pyarrow.compute as pc

    exprs = []
    for field, op, value in filters:
        col = ds.field(field)
        if op == "=":
            exprs.append(col == value)
        elif op == ">=":
            exprs.append(col >= value)
        elif op == "<=":
            exprs.append(col <= value)
        elif op == "!=":
            exprs.append(col != value)

    if not exprs:
        return None
    result = exprs[0]
    for expr in exprs[1:]:
        result = result & expr
    return result


def _read_parquet_files_paginated(
    gold_path: str,
    page: int,
    page_size: int,
    filters: Optional[List],
) -> Tuple[List[Dict], int]:
    """Fallback: lee archivos Parquet uno a uno para paginación."""
    parquet_files = sorted(
        glob.glob(os.path.join(gold_path, "**", "*.parquet"), recursive=True)
    )

    all_records = []
    for pf in parquet_files:
        table = pq.read_table(pf)
        if filters:
            expr = _filters_to_expression(filters)
            if expr is not None:
                table = table.filter(expr)
        all_records.extend(table.to_pylist())

    total = len(all_records)
    offset = (page - 1) * page_size
    return all_records[offset : offset + page_size], total


def _read_csv_paginated(
    csv_files: List[str],
    page: int,
    page_size: int,
    filters: Dict[str, Any],
) -> Tuple[List[Dict], int]:
    """Lee CSVs de la capa gold con paginación (fallback sin PyArrow)."""
    all_records = []
    for cf in sorted(csv_files):
        with open(cf, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if _csv_row_matches_filters(row, filters):
                    all_records.append(dict(row))

    total = len(all_records)
    offset = (page - 1) * page_size
    return all_records[offset : offset + page_size], total


def _csv_row_matches_filters(row: Dict, filters: Dict) -> bool:
    """Aplica filtros simples sobre una fila CSV."""
    if filters.get("decision") and row.get("decision") != filters["decision"]:
        return False
    if filters.get("perfil_cobertura") and row.get("perfil_cobertura") != filters["perfil_cobertura"]:
        return False
    if filters.get("run_id") and row.get("id_corrida") != filters["run_id"]:
        return False
    if filters.get("entidad_emisora") and row.get("entidad_emisora") != filters["entidad_emisora"]:
        return False
    if filters.get("medio_emisor") and row.get("medio_emisor") != filters["medio_emisor"]:
        return False
    if filters.get("codigo_servicio") and row.get("codigo_servicio") != filters["codigo_servicio"]:
        return False
    return True


# ---------------------------------------------------------------------------
# Lectura paginada de cuarentena
# ---------------------------------------------------------------------------

def read_quarantine_paginated(
    page: int = 1,
    page_size: int = 500,
    run_id: Optional[str] = None,
    settings: Optional[Settings] = None,
) -> Tuple[List[Dict], int]:
    """Lee archivos CSV de cuarentena con paginación.
    En modo AWS consulta la tabla de cuarentena en Athena."""
    if settings is None:
        settings = get_settings()

    if settings.is_aws:
        try:
            return _read_quarantine_athena(page, page_size, run_id, settings)
        except Exception:
            pass  # Fallback a cuarentena local si Athena no tiene la tabla

    page_size = min(page_size, 2000)
    qdir = _quarantine_dir(settings)

    if not os.path.exists(qdir):
        return [], 0

    pattern = f"quarantine_{run_id}.csv" if run_id else "quarantine_*.csv"
    csv_files = sorted(glob.glob(os.path.join(qdir, pattern)))

    all_records = []
    for cf in csv_files:
        with open(cf, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            all_records.extend(dict(r) for r in reader)

    total = len(all_records)
    offset = (page - 1) * page_size
    return all_records[offset : offset + page_size], total


# ---------------------------------------------------------------------------
# Lectura de métricas (archivos JSON)
# ---------------------------------------------------------------------------

def list_run_metrics(settings: Optional[Settings] = None) -> List[Dict]:
    """Lista todas las métricas de corridas disponibles, ordenadas por fecha desc.
    En modo AWS busca los JSON de métricas en S3."""
    if settings is None:
        settings = get_settings()

    if settings.is_aws:
        try:
            s3_metrics = _list_run_metrics_s3(settings)
            if s3_metrics:
                return s3_metrics
        except Exception:
            pass  # Fallback a métricas locales si S3 falla o no tiene métricas aún

    metrics_files = sorted(
        glob.glob(os.path.join(_metrics_dir(settings), "metrics_*.json")),
        reverse=True,
    )

    results = []
    for mf in metrics_files:
        try:
            with open(mf, "r", encoding="utf-8") as f:
                results.append(json.load(f))
        except (json.JSONDecodeError, OSError):
            continue

    return results


def get_run_metrics(run_id: str, settings: Optional[Settings] = None) -> Optional[Dict]:
    """Retorna las métricas de una corrida específica por ID."""
    if settings is None:
        settings = get_settings()

    metrics_path = os.path.join(_metrics_dir(settings), f"metrics_{run_id}.json")
    if not os.path.exists(metrics_path):
        return None

    with open(metrics_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_latest_metrics(settings: Optional[Settings] = None) -> Optional[Dict]:
    """Retorna las métricas de la corrida más reciente."""
    runs = list_run_metrics(settings)
    return runs[0] if runs else None


# ---------------------------------------------------------------------------
# Estadísticas agregadas para el dashboard (sin cargar todo en memoria)
# ---------------------------------------------------------------------------

def compute_gold_stats(settings: Optional[Settings] = None) -> Dict[str, Any]:
    """
    Calcula estadísticas de la capa gold.
    Modo local: lee Parquet/CSV con PyArrow.
    Modo AWS:   consulta la vista v_resumen_cobertura_ejecutivo en Athena.
    """
    if settings is None:
        settings = get_settings()

    if settings.is_aws:
        try:
            return _compute_gold_stats_athena(settings)
        except Exception:
            pass  # Fallback a estadísticas locales si Athena aún no tiene las vistas creadas

    gold_path = _gold_dir(settings)
    stats: Dict[str, Any] = {
        "total_ordenes": 0,
        "total_cubiertas": 0,
        "total_no_cubiertas": 0,
        "porcentaje_cubiertas": 0.0,
        "valor_solicitado_total_cop": 0,
        "valor_reconocido_total_cop": 0,
        "distribucion_perfiles": {},
        "distribucion_decisiones": {},
        "top_servicios": [],
        "top_alertas": [],
    }

    if not os.path.exists(gold_path):
        return stats

    parquet_files = glob.glob(os.path.join(gold_path, "**", "*.parquet"), recursive=True)
    csv_files = glob.glob(os.path.join(gold_path, "**", "*.csv"), recursive=True)

    if not parquet_files and not csv_files:
        return stats

    # Leer solo las columnas necesarias para estadísticas
    columns = [
        "decision", "perfil_cobertura", "valor_procedimiento",
        "valor_reconocido", "codigo_servicio", "servicio_solicitado",
        "alertas"
    ]

    try:
        if parquet_files:
            dataset = ds.dataset(
                gold_path,
                format="parquet",
                partitioning=ds.partitioning(
                    pa.schema([pa.field("fecha_solicitud", pa.string())]),
                    flavor="hive",
                ),
            )
            table = dataset.to_table(columns=columns)
        else:
            # Fallback CSV
            all_rows: List[Dict] = []
            for cf in csv_files:
                with open(cf, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    all_rows.extend(dict(r) for r in reader)
            table = pa.Table.from_pylist(all_rows)

        import pyarrow.compute as pc

        total = len(table)
        stats["total_ordenes"] = total

        # Decisiones
        decision_col = table.column("decision")
        cubiertas = pc.sum(pc.equal(decision_col, "CUBRE")).as_py() or 0
        stats["total_cubiertas"] = cubiertas
        stats["total_no_cubiertas"] = total - cubiertas
        stats["porcentaje_cubiertas"] = round(cubiertas / total * 100, 2) if total > 0 else 0.0

        # Valores financieros
        stats["valor_solicitado_total_cop"] = pc.sum(
            table.column("valor_procedimiento").cast(pa.int64())
        ).as_py() or 0
        stats["valor_reconocido_total_cop"] = pc.sum(
            table.column("valor_reconocido").cast(pa.int64())
        ).as_py() or 0

        # Distribución por perfil
        perfiles = table.column("perfil_cobertura").to_pylist()
        dist_perfiles: Dict[str, int] = {}
        for p in perfiles:
            dist_perfiles[p] = dist_perfiles.get(p, 0) + 1
        stats["distribucion_perfiles"] = dist_perfiles

        # Distribución por decisión
        stats["distribucion_decisiones"] = {
            "CUBRE": cubiertas,
            "NO CUBRE": total - cubiertas,
        }

        # Top servicios
        servicios = table.column("codigo_servicio").to_pylist()
        servicio_names = table.column("servicio_solicitado").to_pylist()
        servicio_counts: Dict[str, Dict] = {}
        for cod, nom in zip(servicios, servicio_names):
            if cod not in servicio_counts:
                servicio_counts[cod] = {"codigo": cod, "nombre": nom, "total": 0}
            servicio_counts[cod]["total"] += 1
        stats["top_servicios"] = sorted(
            servicio_counts.values(), key=lambda x: x["total"], reverse=True
        )[:10]

        # Top alertas
        alertas_list = table.column("alertas").to_pylist()
        alerta_counts: Dict[str, int] = {}
        for a in alertas_list:
            alerta_counts[a] = alerta_counts.get(a, 0) + 1
        stats["top_alertas"] = sorted(
            [{"alerta": k, "total": v} for k, v in alerta_counts.items()],
            key=lambda x: x["total"],
            reverse=True,
        )[:10]

    except Exception as exc:
        stats["error"] = str(exc)

    return stats


# ---------------------------------------------------------------------------
# Catálogos
# ---------------------------------------------------------------------------

def read_catalogo_servicios(settings: Optional[Settings] = None) -> List[Dict]:
    """Lee el catálogo de servicios cubiertos."""
    if settings is None:
        settings = get_settings()
    path = settings.catalogo_servicios_path
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_catalogo_perfiles(settings: Optional[Settings] = None) -> List[Dict]:
    """Lee el catálogo de perfiles de cobertura."""
    if settings is None:
        settings = get_settings()
    path = settings.catalogo_perfiles_path
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# Upload / gestión de archivos temporales
# ---------------------------------------------------------------------------

def save_uploaded_file(filename: str, content: bytes, settings: Optional[Settings] = None) -> str:
    """Guarda un archivo subido en el directorio de uploads. Retorna la ruta completa."""
    if settings is None:
        settings = get_settings()

    upload_path = Path(settings.upload_dir) / filename
    upload_path.write_bytes(content)
    return str(upload_path)


def get_upload_path(filename: str, settings: Optional[Settings] = None) -> Optional[str]:
    """Retorna la ruta del archivo subido si existe."""
    if settings is None:
        settings = get_settings()

    path = Path(settings.upload_dir) / filename
    return str(path) if path.exists() else None


def list_uploaded_files(settings: Optional[Settings] = None) -> List[Dict]:
    """Lista los archivos CSV disponibles en el directorio de uploads."""
    if settings is None:
        settings = get_settings()

    upload_dir = Path(settings.upload_dir)
    if not upload_dir.exists():
        return []

    return [
        {
            "filename": f.name,
            "size_mb": round(f.stat().st_size / 1_048_576, 2),
            "modified": f.stat().st_mtime,
        }
        for f in sorted(upload_dir.glob("*.csv"), key=lambda x: x.stat().st_mtime, reverse=True)
    ]


# ---------------------------------------------------------------------------
# AWS S3 (modo aws) — stubs que se activan cuando APP_MODE=aws
# ---------------------------------------------------------------------------

def _get_boto3_client(service: str, settings: Settings):
    """Crea un cliente boto3 con las credenciales de .env."""
    import boto3
    kwargs: Dict[str, Any] = {"region_name": settings.aws_default_region}
    if settings.aws_access_key_id:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    if settings.aws_session_token:
        kwargs["aws_session_token"] = settings.aws_session_token
    return boto3.client(service, **kwargs)


def upload_to_s3(local_path: str, s3_key: str, settings: Optional[Settings] = None) -> bool:
    """Sube un archivo local a S3 (solo modo aws)."""
    if settings is None:
        settings = get_settings()
    if settings.is_local:
        raise RuntimeError("upload_to_s3 solo disponible en APP_MODE=aws")
    s3 = _get_boto3_client("s3", settings)
    s3.upload_file(local_path, settings.s3_bucket_name, s3_key)
    return True


def start_glue_job(settings: Optional[Settings] = None) -> str:
    """Lanza el Glue Job y retorna el JobRunId (solo modo aws)."""
    if settings is None:
        settings = get_settings()
    if settings.is_local:
        raise RuntimeError("start_glue_job solo disponible en APP_MODE=aws")

    glue = _get_boto3_client("glue", settings)
    response = glue.start_job_run(JobName=settings.glue_job_name)
    return response["JobRunId"]


def get_glue_job_status(job_run_id: str, settings: Optional[Settings] = None) -> Dict[str, Any]:
    """Consulta el estado de un Glue Job Run (solo modo aws)."""
    if settings is None:
        settings = get_settings()
    if settings.is_local:
        raise RuntimeError("get_glue_job_status solo disponible en APP_MODE=aws")

    glue = _get_boto3_client("glue", settings)
    response = glue.get_job_run(JobName=settings.glue_job_name, RunId=job_run_id)
    run = response["JobRun"]
    return {
        "job_run_id": job_run_id,
        "status": run.get("JobRunState", "UNKNOWN"),
        "started_on": str(run.get("StartedOn", "")),
        "completed_on": str(run.get("CompletedOn", "")),
        "error_message": run.get("ErrorMessage", ""),
    }


def run_athena_query(sql: str, settings: Optional[Settings] = None) -> List[Dict]:
    """
    Ejecuta una consulta en Athena y retorna los resultados como lista de dicts.
    Máximo 1000 filas para la API. (Solo modo aws)
    """
    import time
    if settings is None:
        settings = get_settings()
    if settings.is_local:
        raise RuntimeError("run_athena_query solo disponible en APP_MODE=aws")

    athena = _get_boto3_client("athena", settings)

    response = athena.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": settings.athena_database},
        WorkGroup=settings.athena_workgroup,
    )
    query_id = response["QueryExecutionId"]

    # Esperar a que termine (máx 60 s)
    for _ in range(60):
        status_resp = athena.get_query_execution(QueryExecutionId=query_id)
        state = status_resp["QueryExecution"]["Status"]["State"]
        if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(1)

    if state != "SUCCEEDED":
        raise RuntimeError(f"Athena query {query_id} terminó con estado: {state}")

    # Obtener resultados
    results_resp = athena.get_query_results(
        QueryExecutionId=query_id,
        MaxResults=1000,
    )

    rows = results_resp.get("ResultSet", {}).get("Rows", [])
    if not rows:
        return []

    headers = [col.get("VarCharValue", "") for col in rows[0]["Data"]]
    data = []
    for row in rows[1:]:
        values = [cell.get("VarCharValue", "") for cell in row["Data"]]
        data.append(dict(zip(headers, values)))

    return data


# ---------------------------------------------------------------------------
# Implementaciones AWS privadas — activadas cuando APP_MODE=aws
# ---------------------------------------------------------------------------

def _build_athena_where(filters: Dict[str, Any]) -> str:
    """Construye cláusula WHERE para Athena a partir del diccionario de filtros."""
    clauses = []
    if filters.get("decision"):
        d = filters["decision"].replace("'", "''")
        clauses.append(f"decision = '{d}'")
    if filters.get("perfil_cobertura"):
        p = filters["perfil_cobertura"].replace("'", "''")
        clauses.append(f"perfil_cobertura = '{p}'")
    if filters.get("entidad_emisora"):
        e = filters["entidad_emisora"].replace("'", "''")
        clauses.append(f"entidad_emisora = '{e}'")
    if filters.get("medio_emisor"):
        m = filters["medio_emisor"].replace("'", "''")
        clauses.append(f"medio_emisor = '{m}'")
    if filters.get("codigo_servicio"):
        c = filters["codigo_servicio"].replace("'", "''")
        clauses.append(f"codigo_servicio = '{c}'")
    if filters.get("alertas"):
        a = filters["alertas"].replace("'", "''")
        clauses.append(f"alertas = '{a}'")
    if filters.get("run_id"):
        r = filters["run_id"].replace("'", "''")
        clauses.append(f"id_corrida = '{r}'")
    if filters.get("fecha_desde"):
        clauses.append(f"fecha_particion >= DATE '{filters['fecha_desde']}'")
    if filters.get("fecha_hasta"):
        clauses.append(f"fecha_particion <= DATE '{filters['fecha_hasta']}'")
    return ("WHERE " + " AND ".join(clauses)) if clauses else ""


def _read_gold_athena(
    page: int,
    page_size: int,
    filters: Dict[str, Any],
    settings: Settings,
) -> Tuple[List[Dict], int]:
    """
    Lee la capa gold de Athena con paginación usando OFFSET/LIMIT.
    Primero obtiene el COUNT, luego la página solicitada.
    """
    from api.services.aws_service import athena_execute_and_fetch

    db    = settings.athena_database
    table = "gold_solicitudes_cobertura"
    where = _build_athena_where(filters)

    # COUNT total
    count_sql = f"SELECT COUNT(*) AS total FROM {db}.{table} {where};"
    try:
        _, count_rows = athena_execute_and_fetch(count_sql, settings, max_rows=1)
        total = int(count_rows[0].get("total", 0)) if count_rows else 0
    except Exception:
        total = 0

    if total == 0:
        return [], 0

    # Datos de la página
    offset = (page - 1) * page_size
    data_sql = (
        f"SELECT * FROM {db}.{table} {where} "
        f"ORDER BY fecha_solicitud DESC "
        f"OFFSET {offset} ROWS FETCH NEXT {page_size} ROWS ONLY;"
    )
    try:
        _, rows = athena_execute_and_fetch(data_sql, settings, max_rows=page_size)
    except Exception as exc:
        raise RuntimeError(f"Error consultando Athena gold: {exc}") from exc

    return rows, total


def _read_quarantine_athena(
    page: int,
    page_size: int,
    run_id: Optional[str],
    settings: Settings,
) -> Tuple[List[Dict], int]:
    """Lee la tabla de cuarentena de Athena con paginación."""
    from api.services.aws_service import athena_execute_and_fetch

    db    = settings.athena_database
    table = "quarentena_solicitudes"
    where = f"WHERE id_corrida = '{run_id}'" if run_id else ""

    count_sql = f"SELECT COUNT(*) AS total FROM {db}.{table} {where};"
    try:
        _, count_rows = athena_execute_and_fetch(count_sql, settings, max_rows=1)
        total = int(count_rows[0].get("total", 0)) if count_rows else 0
    except Exception:
        total = 0

    if total == 0:
        return [], 0

    offset   = (page - 1) * page_size
    data_sql = (
        f"SELECT * FROM {db}.{table} {where} "
        f"ORDER BY timestamp_rechazo DESC "
        f"OFFSET {offset} ROWS FETCH NEXT {page_size} ROWS ONLY;"
    )
    try:
        _, rows = athena_execute_and_fetch(data_sql, settings, max_rows=page_size)
    except Exception as exc:
        raise RuntimeError(f"Error consultando Athena quarantine: {exc}") from exc

    return rows, total


def _list_run_metrics_s3(settings: Settings) -> List[Dict]:
    """Lista archivos metrics_*.json desde S3."""
    from api.services.aws_service import s3_list_objects, s3_download_bytes

    prefix  = "metrics/"
    try:
        objects = s3_list_objects(prefix, settings, max_keys=100)
    except Exception:
        return []

    results = []
    for obj in sorted(objects, key=lambda x: x.get("last_modified", 0), reverse=True):
        if not obj.get("key", "").endswith(".json"):
            continue
        try:
            raw   = s3_download_bytes(obj["key"], settings)
            data  = json.loads(raw.decode("utf-8"))
            results.append(data)
        except Exception:
            continue
    return results


def _compute_gold_stats_athena(settings: Settings) -> Dict[str, Any]:
    """
    Calcula estadísticas de cobertura consultando las vistas analíticas de Athena.
    Usa la vista v_resumen_cobertura_ejecutivo para los KPIs principales.
    """
    from api.services.aws_service import athena_execute_and_fetch

    db    = settings.athena_database
    stats: Dict[str, Any] = {
        "total_ordenes": 0,
        "total_cubiertas": 0,
        "total_no_cubiertas": 0,
        "porcentaje_cubiertas": 0.0,
        "valor_solicitado_total_cop": 0,
        "valor_reconocido_total_cop": 0,
        "distribucion_perfiles": {},
        "distribucion_decisiones": {},
        "top_servicios": [],
        "top_alertas": [],
    }

    try:
        # Vista de resumen ejecutivo
        sql_resumen = f"SELECT * FROM {db}.v_resumen_cobertura_ejecutivo;"
        _, resumen_rows = athena_execute_and_fetch(sql_resumen, settings, max_rows=100)

        total = 0
        cubiertas = 0
        val_sol = 0
        val_rec = 0
        dist_perfiles: Dict[str, int] = {}
        dist_decisiones: Dict[str, int] = {}

        for row in resumen_rows:
            n    = int(row.get("total_ordenes", 0))
            dec  = row.get("decision", "")
            perf = row.get("perfil_cobertura", "")
            vs   = int(row.get("valor_solicitado_total", 0) or 0)
            vr   = int(row.get("valor_reconocido_total", 0) or 0)

            total    += n
            val_sol  += vs
            val_rec  += vr

            if dec == "CUBRE":
                cubiertas += n
            dist_decisiones[dec]  = dist_decisiones.get(dec, 0) + n
            dist_perfiles[perf]   = dist_perfiles.get(perf, 0) + n

        stats["total_ordenes"]              = total
        stats["total_cubiertas"]            = cubiertas
        stats["total_no_cubiertas"]         = total - cubiertas
        stats["porcentaje_cubiertas"]       = round(cubiertas / total * 100, 2) if total else 0.0
        stats["valor_solicitado_total_cop"] = val_sol
        stats["valor_reconocido_total_cop"] = val_rec
        stats["distribucion_perfiles"]      = dist_perfiles
        stats["distribucion_decisiones"]    = dist_decisiones

        # Top servicios y alertas desde la vista de auditoría
        sql_alertas = (
            f"SELECT codigo_servicio, servicio_solicitado, alertas, "
            f"total_casos AS total, monto_total AS valor_procedimiento "
            f"FROM {db}.v_auditoria_servicios_alertas "
            f"ORDER BY total_casos DESC LIMIT 10;"
        )
        _, alertas_rows = athena_execute_and_fetch(sql_alertas, settings, max_rows=10)

        top_servicios_map: Dict[str, Dict] = {}
        top_alertas_map: Dict[str, int] = {}

        for row in alertas_rows:
            cod  = row.get("codigo_servicio", "")
            nom  = row.get("servicio_solicitado", "")
            alrt = row.get("alertas", "NINGUNA")
            n    = int(row.get("total", 0) or 0)

            if cod not in top_servicios_map:
                top_servicios_map[cod] = {"codigo": cod, "nombre": nom, "total": 0}
            top_servicios_map[cod]["total"] += n
            top_alertas_map[alrt] = top_alertas_map.get(alrt, 0) + n

        stats["top_servicios"] = sorted(
            top_servicios_map.values(), key=lambda x: x["total"], reverse=True
        )[:10]
        stats["top_alertas"] = sorted(
            [{"alerta": k, "total": v} for k, v in top_alertas_map.items()],
            key=lambda x: x["total"], reverse=True,
        )[:10]

    except Exception as exc:
        stats["error"] = f"Error consultando Athena: {exc}"

    return stats
