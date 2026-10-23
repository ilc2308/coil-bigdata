"""
aws_glue_job.py
Script oficial para AWS Glue Job (Apache Spark 3.3+ / Glue 4.0 / 5.0).
Procesamiento distribuido masivo de órdenes médicas para el Sistema de Salud de Chernovia.
Cumple con requerimientos de la licitación: escalabilidad hasta 12M de órdenes en < 2h.
"""

import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql import functions as F
from pyspark.sql.types import *

def main():
    # 1. Parámetros del Job en AWS Glue
    args = getResolvedOptions(
        sys.argv,
        [
            'JOB_NAME',
            'S3_BUCKET_NAME',
            'SOURCE_PREFIX',
            'TARGET_PREFIX',
            'QUARANTINE_PREFIX',
            'VERSION_CATALOGO'
        ]
    )
    
    sc = SparkContext.getOrCreate()
    glueContext = GlueContext(sc)
    spark = glueContext.spark_session
    job = Job(glueContext)
    job.init(args['JOB_NAME'], args)
    
    bucket = args['S3_BUCKET_NAME']
    source_path = f"s3://{bucket}/{args['SOURCE_PREFIX']}"
    target_gold_path = f"s3://{bucket}/{args['TARGET_PREFIX']}"
    quarantine_path = f"s3://{bucket}/{args['QUARANTINE_PREFIX']}"
    version_cat = args.get('VERSION_CATALOGO', '2026.1')
    
    print(f"Iniciando Glue Job: {args['JOB_NAME']}")
    print(f"Leyendo datos desde: {source_path}")
    
    # 2. Cargar Dataset Crudo desde Capa Bronze (S3)
    raw_df = spark.read \
        .option("header", "true") \
        .option("encoding", "UTF-8") \
        .csv(source_path)
    
    # Añadir timestamp de auditoría e identificador de corrida
    run_id = f"GLUE-{spark.sparkContext.applicationId}"
    current_ts = F.current_timestamp()
    
    # 3. Validación de esquema y separación a Cuarentena
    # Una glosa válida debe contener los separadores esperados
    is_valid_glosa = (
        F.col("glosa").isNotNull() &
        F.col("glosa").contains("Paciente:") &
        F.col("glosa").contains("DNO:") &
        F.col("glosa").contains("PerfilCobertura:") &
        F.col("glosa").contains("ServicioSolicitado:")
    )
    
    is_valid_valor = (
        F.col("valor_procedimiento").isNotNull() &
        (F.col("valor_procedimiento").cast("bigint") > 0)
    )
    
    valid_filter = is_valid_glosa & is_valid_valor
    
    # Registros a cuarentena
    quarantine_df = raw_df.filter(~valid_filter).select(
        F.col("id_solicitud"),
        F.col("fecha_solicitud"),
        F.col("glosa"),
        F.col("medio_emisor"),
        F.col("valor_procedimiento"),
        F.col("entidad_emisora"),
        F.when(~is_valid_glosa, "Glosa malformada o incompleta")
         .otherwise("Valor de procedimiento inválido").alias("motivo_rechazo"),
        F.lit(run_id).alias("id_corrida"),
        current_ts.alias("timestamp_rechazo")
    )
    
    # Escribir cuarentena en formato CSV
    quarantine_df.write \
        .mode("append") \
        .option("header", "true") \
        .csv(quarantine_path)
    
    # 4. Procesamiento de Registros Válidos
    valid_df = raw_df.filter(valid_filter)
    
    # Extracción de campos de la glosa mediante expresiones regulares nativas de Spark (Catalyst Optimizer)
    parsed_df = valid_df.select(
        F.col("id_solicitud"),
        F.col("fecha_solicitud"),
        F.to_date(F.col("fecha_solicitud")).alias("fecha_particion"),
        F.col("medio_emisor"),
        F.col("entidad_emisora"),
        F.col("valor_procedimiento").cast("bigint").alias("valor_procedimiento"),
        F.trim(F.regexp_extract(F.col("glosa"), r"Paciente:\s*([^;]+);", 1)).alias("paciente"),
        F.trim(F.regexp_extract(F.col("glosa"), r"DNO:\s*([^;]+);", 1)).alias("dno"),
        F.trim(F.regexp_extract(F.col("glosa"), r"SeguroSocial:\s*([^;]+);", 1)).alias("seguro_social"),
        F.trim(F.regexp_extract(F.col("glosa"), r"Edad:\s*([^;]+);", 1)).cast("int").alias("edad"),
        F.upper(F.trim(F.regexp_extract(F.col("glosa"), r"PerfilCobertura:\s*([^;]+);", 1))).alias("perfil_cobertura"),
        F.trim(F.regexp_extract(F.col("glosa"), r"ServicioSolicitado:\s*([^;]+);", 1)).alias("servicio_solicitado"),
        F.trim(F.regexp_extract(F.col("glosa"), r"Medicacion:\s*(.*)", 1)).alias("medicaciones")
    )
    
    # 5. Carga de Catálogos y Broadcast Joins
    catalog_servicios_path = f"s3://{bucket}/catalogs/COIL_catalogo_servicios_cubiertos.csv"
    catalog_perfiles_path = f"s3://{bucket}/catalogs/COIL_catalogo_perfiles_cobertura.csv"
    
    cat_servicios_df = spark.read.option("header", "true").csv(catalog_servicios_path)
    cat_servicios_clean = cat_servicios_df.select(
        F.lower(F.trim(F.col("servicio"))).alias("cat_servicio_key"),
        F.col("codigo_servicio"),
        F.col("categoria").alias("categoria_servicio"),
        F.col("valor_min_referencia").cast("bigint"),
        F.col("valor_max_referencia").cast("bigint"),
        F.col("medicaciones_referencia")
    )
    
    # Cruce con catálogo de servicios mediante broadcast join
    joined_df = parsed_df.join(
        F.broadcast(cat_servicios_clean),
        F.lower(parsed_df.servicio_solicitado) == cat_servicios_clean.cat_servicio_key,
        how="left"
    )
    
    # 6. Cálculo de Cobertura y Porcentaje de Negocio
    # Regla: PRIORITARIO 100%, ESTANDAR 50%, COPAGO 25%, NO CUBIERTO 0%
    is_covered = F.col("codigo_servicio").isNotNull()
    
    calculated_df = joined_df.withColumn(
        "decision",
        F.when(is_covered, F.lit("CUBRE")).otherwise(F.lit("NO CUBRE"))
    ).withColumn(
        "porcentaje_cobertura",
        F.when(is_covered,
            F.when(F.col("perfil_cobertura") == "PRIORITARIO", F.lit(100))
             .when(F.col("perfil_cobertura") == "ESTANDAR", F.lit(50))
             .when(F.col("perfil_cobertura") == "COPAGO", F.lit(25))
             .otherwise(F.lit(0))
        ).otherwise(F.lit(0))
    ).withColumn(
        "valor_reconocido",
        F.round(F.col("valor_procedimiento") * (F.col("porcentaje_cobertura") / 100.0)).cast("bigint")
    ).withColumn(
        "regla_aplicada",
        F.when(is_covered, F.lit("RN-COV-CATALOGO-V1")).otherwise(F.lit("RN-NOCOV-EXCLUSION-V1"))
    ).withColumn(
        "codigo_servicio",
        F.coalesce(F.col("codigo_servicio"), F.lit("NON-COVERED"))
    ).withColumn(
        "categoria_servicio",
        F.coalesce(F.col("categoria_servicio"), F.lit("No Cubierto"))
    )
    
    # 7. Privacidad y Seudonimización con SHA-256 (Ley 1581 / RNF-09)
    gold_df = calculated_df.select(
        F.col("id_solicitud"),
        F.col("fecha_solicitud"),
        F.col("fecha_particion"),
        F.col("medio_emisor"),
        F.col("entidad_emisora"),
        F.col("edad"),
        F.col("perfil_cobertura"),
        F.col("servicio_solicitado"),
        F.col("codigo_servicio"),
        F.col("categoria_servicio"),
        F.col("medicaciones"),
        F.col("decision"),
        F.col("porcentaje_cobertura"),
        F.col("valor_procedimiento"),
        F.col("valor_reconocido"),
        F.col("regla_aplicada"),
        F.lit(version_cat).alias("version_catalogo"),
        # Alertas de referencia
        F.when(
            is_covered & (F.col("valor_procedimiento") < F.col("valor_min_referencia")), F.lit("VALOR_BAJO_RANGO")
        ).when(
            is_covered & (F.col("valor_procedimiento") > F.col("valor_max_referencia")), F.lit("VALOR_SOBRE_RANGO")
        ).when(~is_covered, F.lit("SERVICIO_FUERA_DE_CATALOGO")).otherwise(F.lit("NINGUNA")).alias("alertas"),
        # Hashes de seguridad para PII
        F.sha2(F.col("dno"), 256).alias("dno_hash"),
        F.sha2(F.col("seguro_social"), 256).alias("seguro_social_hash"),
        F.sha2(F.col("paciente"), 256).alias("paciente_hash"),
        F.lit(run_id).alias("id_corrida"),
        current_ts.alias("timestamp_procesamiento")
    )
    
    # 8. Escritura en Capa Gold (S3 Parquet con compresión Snappy particionado por fecha)
    print(f"Escribiendo resultados en Capa Gold: {target_gold_path}")
    gold_df.write \
        .mode("append") \
        .partitionBy("fecha_particion") \
        .option("compression", "snappy") \
        .parquet(target_gold_path)
        
    print("Glue Job finalizado con éxito.")
    job.commit()

if __name__ == '__main__':
    main()
