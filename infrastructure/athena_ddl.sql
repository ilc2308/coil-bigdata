-- ============================================================================
-- DDL Y CONSULTAS ANALÍTICAS PARA AMAZON ATHENA
-- Sistema de Salud de Chernovia - Auditoría Masiva de Cobertura
-- ============================================================================

CREATE DATABASE IF NOT EXISTS coil_bigdata_salud_db
LOCATION 's3://${S3_BUCKET_NAME}/databases/coil_bigdata_salud_db/';

-- ----------------------------------------------------------------------------
-- 1. TABLA CAPA GOLD (RESULTADOS PROCESADOS, PARQUET, PARTICIONADA POR FECHA)
-- ----------------------------------------------------------------------------
CREATE EXTERNAL TABLE IF NOT EXISTS coil_bigdata_salud_db.gold_solicitudes_cobertura (
    id_solicitud STRING,
    fecha_solicitud STRING,
    medio_emisor STRING,
    entidad_emisora STRING,
    edad INT,
    perfil_cobertura STRING,
    servicio_solicitado STRING,
    codigo_servicio STRING,
    categoria_servicio STRING,
    medicaciones STRING,
    decision STRING,
    porcentaje_cobertura INT,
    valor_procedimiento BIGINT,
    valor_reconocido BIGINT,
    regla_aplicada STRING,
    version_catalogo STRING,
    alertas STRING,
    dno_hash STRING,
    seguro_social_hash STRING,
    paciente_hash STRING,
    id_corrida STRING,
    timestamp_procesamiento TIMESTAMP
)
PARTITIONED BY (fecha_particion DATE)
STORED AS PARQUET
LOCATION 's3://${S3_BUCKET_NAME}/gold/curated_solicitudes/'
TBLPROPERTIES ('parquet.compression'='SNAPPY');

-- Para cargar las particiones automáticamente en Athena:
-- MSCK REPAIR TABLE coil_bigdata_salud_db.gold_solicitudes_cobertura;

-- ----------------------------------------------------------------------------
-- 2. TABLA CAPA CUARENTENA (REGISTROS INVÁLIDOS O RECHAZADOS POR ESQUEMA)
-- ----------------------------------------------------------------------------
CREATE EXTERNAL TABLE IF NOT EXISTS coil_bigdata_salud_db.quarentena_solicitudes (
    id_solicitud STRING,
    fecha_solicitud STRING,
    glosa STRING,
    medio_emisor STRING,
    valor_procedimiento STRING,
    entidad_emisora STRING,
    motivo_rechazo STRING,
    id_corrida STRING,
    timestamp_rechazo TIMESTAMP
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION 's3://${S3_BUCKET_NAME}/quarantine/solicitudes/'
TBLPROPERTIES ("skip.header.line.count"="1");

-- ----------------------------------------------------------------------------
-- 3. VISTAS ANALÍTICAS PARA AUDITORÍA Y DASHBOARD EJECUTIVO (RF-10, RF-15)
-- ----------------------------------------------------------------------------

-- Vista A: Consolidado de Cobertura e Impacto Presupuestal
CREATE OR REPLACE VIEW coil_bigdata_salud_db.v_resumen_cobertura_ejecutivo AS
SELECT 
    decision,
    perfil_cobertura,
    COUNT(*) AS total_ordenes,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) AS porcentaje_ordenes,
    SUM(valor_procedimiento) AS valor_solicitado_total,
    SUM(valor_reconocido) AS valor_reconocido_total,
    ROUND(SUM(valor_reconocido) * 100.0 / SUM(valor_solicitado_total), 2) AS porcentaje_efectivo_pago
FROM coil_bigdata_salud_db.gold_solicitudes_cobertura
GROUP BY decision, perfil_cobertura;

-- Vista B: Análisis de Demanda y Gasto por Canal y Entidad Emisora
CREATE OR REPLACE VIEW coil_bigdata_salud_db.v_analisis_canal_entidad AS
SELECT 
    entidad_emisora,
    medio_emisor,
    COUNT(*) AS volumen_solicitudes,
    SUM(CASE WHEN decision = 'CUBRE' THEN 1 ELSE 0 END) AS cubiertas,
    SUM(CASE WHEN decision = 'NO CUBRE' THEN 1 ELSE 0 END) AS no_cubiertas,
    SUM(valor_procedimiento) AS monto_solicitado,
    SUM(valor_reconocido) AS monto_reconocido
FROM coil_bigdata_salud_db.gold_solicitudes_cobertura
GROUP BY entidad_emisora, medio_emisor;

-- Vista C: Top Servicios Solicitados y Detección de Alertas de Auditoría
CREATE OR REPLACE VIEW coil_bigdata_salud_db.v_auditoria_servicios_alertas AS
SELECT 
    codigo_servicio,
    servicio_solicitado,
    categoria_servicio,
    alertas,
    COUNT(*) AS total_casos,
    SUM(valor_procedimiento) AS monto_total,
    SUM(valor_reconocido) AS monto_pagado
FROM coil_bigdata_salud_db.gold_solicitudes_cobertura
GROUP BY codigo_servicio, servicio_solicitado, categoria_servicio, alertas;
