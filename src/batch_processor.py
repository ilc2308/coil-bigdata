"""
batch_processor.py
Procesador distribuible por lotes para órdenes médicas (Sistema de Salud de Chernovia).
Diseñado para alta velocidad, trazabilidad completa, conciliación de integridad y tolerancia a fallos.
Cumple con RF-01 hasta RF-13 y RNF-01 hasta RNF-13.
"""

import os
import sys
import csv
import json
import time
import uuid
import datetime
from typing import Dict, Any, List

from src.utils.glosa_parser import parse_glosa
from src.utils.rule_engine import CoverageRuleEngine

def process_batch(
    input_csv_path: str,
    catalogo_servicios_path: str,
    catalogo_perfiles_path: str,
    output_dir: str,
    run_id: str = None,
    chunk_size: int = 100000
) -> Dict[str, Any]:
    """
    Ejecuta el procesamiento por lotes sobre el archivo de solicitudes.
    """
    start_time = time.time()
    
    if not run_id:
        run_id = f"RUN-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
        
    engine = CoverageRuleEngine(catalogo_servicios_path, catalogo_perfiles_path)
    
    curated_dir = os.path.join(output_dir, "gold_curated")
    quarantine_dir = os.path.join(output_dir, "quarantine")
    os.makedirs(curated_dir, exist_ok=True)
    os.makedirs(quarantine_dir, exist_ok=True)
    
    total_recibidas = 0
    total_procesadas = 0
    total_cubiertas = 0
    total_no_cubiertas = 0
    total_cuarentena = 0
    valor_solicitado_total = 0
    valor_reconocido_total = 0
    
    perfiles_stats = {"PRIORITARIO": 0, "ESTANDAR": 0, "COPAGO": 0}
    
    # Manejadores de particiones por fecha para escritura eficiente
    partition_writers = {}
    partition_files = {}
    
    # Archivo de cuarentena
    quarantine_file_path = os.path.join(quarantine_dir, f"quarantine_{run_id}.csv")
    quarantine_file = open(quarantine_file_path, 'w', encoding='utf-8', newline='')
    quarantine_writer = csv.writer(quarantine_file)
    quarantine_writer.writerow([
        "id_solicitud", "fecha_solicitud", "glosa_raw", "medio_emisor", 
        "valor_procedimiento", "entidad_emisora", "motivo_rechazo", "id_corrida", "timestamp_rechazo"
    ])
    
    fieldnames_curated = [
        "id_solicitud", "fecha_solicitud", "fecha_particion", "medio_emisor", "entidad_emisora",
        "edad", "perfil_cobertura", "servicio_solicitado", "codigo_servicio", "categoria_servicio",
        "medicaciones", "decision", "porcentaje_cobertura", "valor_procedimiento", "valor_reconocido",
        "regla_aplicada", "version_catalogo", "alertas", "dno_hash", "seguro_social_hash", "paciente_hash",
        "id_corrida", "timestamp_procesamiento"
    ]
    
    timestamp_iso = datetime.datetime.now().isoformat()
    
    print(f"[{datetime.datetime.now()}] Iniciando corrida {run_id}...")
    print(f"Fuente de datos: {input_csv_path}")
    
    try:
        with open(input_csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                total_recibidas += 1
                
                # Validación básica de esquema y valor
                id_solicitud = row.get('id_solicitud', '').strip()
                fecha_solicitud = row.get('fecha_solicitud', '').strip()
                glosa_raw = row.get('glosa', '').strip()
                medio_emisor = row.get('medio_emisor', '').strip()
                entidad_emisora = row.get('entidad_emisora', '').strip()
                valor_raw = row.get('valor_procedimiento', '').strip()
                
                try:
                    valor_procedimiento = int(valor_raw)
                    if valor_procedimiento <= 0:
                        raise ValueError("Valor menor o igual a cero")
                except (ValueError, TypeError):
                    total_cuarentena += 1
                    quarantine_writer.writerow([
                        id_solicitud, fecha_solicitud, glosa_raw, medio_emisor, 
                        valor_raw, entidad_emisora, "Valor de procedimiento inválido o no numérico", run_id, timestamp_iso
                    ])
                    continue
                
                valor_solicitado_total += valor_procedimiento
                
                # Parseo de glosa
                es_valido, datos_glosa, motivo_error = parse_glosa(glosa_raw)
                if not es_valido:
                    total_cuarentena += 1
                    quarantine_writer.writerow([
                        id_solicitud, fecha_solicitud, glosa_raw, medio_emisor, 
                        valor_procedimiento, entidad_emisora, motivo_error, run_id, timestamp_iso
                    ])
                    continue
                
                # Evaluación de reglas de cobertura
                eval_res = engine.evaluate_order(
                    servicio_solicitado=datos_glosa['servicio_solicitado'],
                    perfil_cobertura=datos_glosa['perfil_cobertura'],
                    valor_procedimiento=valor_procedimiento,
                    medicaciones=datos_glosa['medicaciones']
                )
                
                # Extracción de fecha para partición YYYY-MM-DD
                fecha_particion = fecha_solicitud.split(' ')[0] if ' ' in fecha_solicitud else fecha_solicitud[:10]
                
                # Obtener o crear writer de partición
                if fecha_particion not in partition_writers:
                    part_folder = os.path.join(curated_dir, f"fecha_solicitud={fecha_particion}")
                    os.makedirs(part_folder, exist_ok=True)
                    part_file_path = os.path.join(part_folder, f"part_{run_id}.csv")
                    p_file = open(part_file_path, 'w', encoding='utf-8', newline='')
                    p_writer = csv.DictWriter(p_file, fieldnames=fieldnames_curated)
                    p_writer.writeheader()
                    partition_files[fecha_particion] = p_file
                    partition_writers[fecha_particion] = p_writer
                    
                curated_record = {
                    "id_solicitud": id_solicitud,
                    "fecha_solicitud": fecha_solicitud,
                    "fecha_particion": fecha_particion,
                    "medio_emisor": medio_emisor,
                    "entidad_emisora": entidad_emisora,
                    "edad": datos_glosa['edad'],
                    "perfil_cobertura": datos_glosa['perfil_cobertura'],
                    "servicio_solicitado": datos_glosa['servicio_solicitado'],
                    "codigo_servicio": eval_res['codigo_servicio'],
                    "categoria_servicio": eval_res['categoria_servicio'],
                    "medicaciones": "|".join(datos_glosa['medicaciones']),
                    "decision": eval_res['decision'],
                    "porcentaje_cobertura": eval_res['porcentaje_cobertura'],
                    "valor_procedimiento": valor_procedimiento,
                    "valor_reconocido": eval_res['valor_reconocido'],
                    "regla_aplicada": eval_res['regla_aplicada'],
                    "version_catalogo": eval_res['version_catalogo'],
                    "alertas": eval_res['alertas'],
                    "dno_hash": datos_glosa['dno_hash'],
                    "seguro_social_hash": datos_glosa['seguro_social_hash'],
                    "paciente_hash": datos_glosa['paciente_hash'],
                    "id_corrida": run_id,
                    "timestamp_procesamiento": timestamp_iso
                }
                
                partition_writers[fecha_particion].writerow(curated_record)
                
                total_procesadas += 1
                if eval_res['decision'] == "CUBRE":
                    total_cubiertas += 1
                else:
                    total_no_cubiertas += 1
                    
                valor_reconocido_total += eval_res['valor_reconocido']
                perfil_act = datos_glosa['perfil_cobertura']
                if perfil_act in perfiles_stats:
                    perfiles_stats[perfil_act] += 1
                    
                if total_recibidas % chunk_size == 0:
                    elapsed = time.time() - start_time
                    tps = total_recibidas / elapsed if elapsed > 0 else 0
                    print(f"  > Procesadas {total_recibidas:,} órdenes | Tiempo: {elapsed:.2f} s | Rendimiento: {tps:,.0f} órdenes/s")
    
    finally:
        quarantine_file.close()
        for p_file in partition_files.values():
            p_file.close()
            
    end_time = time.time()
    total_duration_sec = end_time - start_time
    throughput_rps = total_recibidas / total_duration_sec if total_duration_sec > 0 else 0
    
    # Estimación de costo en AWS Glue (1 DPU = $0.308/h; corrida típica 2 DPUs)
    glue_dpu_hours = (2 * total_duration_sec) / 3600.0
    cost_estimate_usd = glue_dpu_hours * 0.308
    
    # Validación de la ecuación de integridad contable (RF-11)
    integridad_cuadrada = (total_recibidas == (total_procesadas + total_cuarentena))
    
    summary = {
        "id_corrida": run_id,
        "timestamp_fin": datetime.datetime.now().isoformat(),
        "duracion_segundos": round(total_duration_sec, 2),
        "rendimiento_ordenes_por_segundo": round(throughput_rps, 2),
        "total_recibidas": total_recibidas,
        "total_procesadas": total_procesadas,
        "total_cubiertas": total_cubiertas,
        "total_no_cubiertas": total_no_cubiertas,
        "total_cuarentena": total_cuarentena,
        "porcentaje_cubiertas": round((total_cubiertas / total_procesadas * 100), 2) if total_procesadas > 0 else 0,
        "valor_solicitado_total_cop": valor_solicitado_total,
        "valor_reconocido_total_cop": valor_reconocido_total,
        "perfiles_distribucion": perfiles_stats,
        "conciliacion_integridad": {
            "recibidas": total_recibidas,
            "procesadas_mas_cuarentena": total_procesadas + total_cuarentena,
            "diferencia": total_recibidas - (total_procesadas + total_cuarentena),
            "estado": "CUADRADA_PERFECTA" if integridad_cuadrada else "ERROR_DESCUADRE"
        },
        "estimacion_costo_aws_usd": round(cost_estimate_usd, 6),
        "cumple_sla_24h": total_duration_sec < 86400,
        "cumple_rendimiento_minimo": throughput_rps >= 139.0
    }
    
    # Guardar métricas de la corrida
    metrics_path = os.path.join(output_dir, f"metrics_{run_id}.json")
    with open(metrics_path, 'w', encoding='utf-8') as mf:
        json.dump(summary, mf, indent=2, ensure_ascii=False)
        
    print(f"\n================ RESUMEN DE EJECUCIÓN ================")
    print(f"ID Corrida: {run_id}")
    print(f"Duración: {total_duration_sec:.2f} s ({total_duration_sec/60:.2f} min)")
    print(f"Rendimiento: {throughput_rps:,.2f} órdenes/s (Meta mínima: >= 139)")
    print(f"Total Recibidas: {total_recibidas:,}")
    print(f"Total Procesadas: {total_procesadas:,} (Cubiertas: {total_cubiertas:,} | No Cubiertas: {total_no_cubiertas:,})")
    print(f"Total Cuarentena: {total_cuarentena:,}")
    print(f"Valor Solicitado Total: ${valor_solicitado_total:,.0f} COP")
    print(f"Valor Reconocido Total: ${valor_reconocido_total:,.0f} COP")
    print(f"Conciliación de Integridad: {summary['conciliacion_integridad']['estado']}")
    print(f"Costo estimado AWS Glue (2 DPUs): ${cost_estimate_usd:.6f} USD")
    print(f"=======================================================\n")
    
    return summary

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    input_file = os.path.join(base_dir, "dataset", "sample_1000.csv")
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        
    servicios = os.path.join(base_dir, "dataset", "COIL_catalogo_servicios_cubiertos.csv")
    perfiles = os.path.join(base_dir, "dataset", "COIL_catalogo_perfiles_cobertura.csv")
    out_dir = os.path.join(base_dir, "output")
    
    process_batch(input_file, servicios, perfiles, out_dir)
