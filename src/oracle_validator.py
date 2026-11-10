"""
oracle_validator.py
Oráculo independiente de validación y verificación de exactitud al 100%.
Comprueba la consistencia matemática, lógica de cobertura, integridad de datos y anonimización.
Cumple con requerimientos RF-10, RNF-05, RNF-06, RNF-09 y RNF-13.
"""

import os
import sys
import csv
import glob
import json
import time
import decimal
from typing import Dict, Any, Optional

def _round_half_up(val: float) -> int:
    d = decimal.Decimal(str(val))
    return int(d.quantize(decimal.Decimal('1'), rounding=decimal.ROUND_HALF_UP))

def run_oracle_validation(
    input_csv_path: str,
    catalogo_servicios_path: str,
    catalogo_perfiles_path: str,
    output_gold_dir: str = "",
    gold_records: Optional[Dict[str, Dict]] = None,
) -> Dict[str, Any]:
    print("=" * 60)
    print("INICIANDO VALIDACIÓN INDEPENDIENTE CON ORÁCULO DE NEGOCIO")
    print("=" * 60)
    t0 = time.time()
    
    # 1. Cargar catálogos en estructuras aisladas del oráculo
    servicios_set = set()
    with open(catalogo_servicios_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            servicios_set.add(row['servicio'].strip().lower())
            
    perfiles_map = {}
    with open(catalogo_perfiles_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            perfiles_map[row['perfil_cobertura'].strip().upper()] = int(row['porcentaje_cobertura_si_el_servicio_esta_cubierto'])

    # 2. Leer o recibir los registros procesados en la capa Gold
    processed_records = {}
    if gold_records is not None:
        processed_records = dict(gold_records)
    elif output_gold_dir:
        # Intentar leer archivos Parquet locales
        parquet_parts = glob.glob(os.path.join(output_gold_dir, "**", "*.parquet"), recursive=True)
        if parquet_parts:
            try:
                import pyarrow.parquet as pq
                for ppart in parquet_parts:
                    table = pq.read_table(ppart)
                    df_p = table.to_pandas()
                    for _, row in df_p.iterrows():
                        processed_records[str(row['id_solicitud'])] = {
                            'id_solicitud': str(row['id_solicitud']),
                            'decision': str(row.get('decision', '')),
                            'porcentaje_cobertura': int(row.get('porcentaje_cobertura', 0)),
                            'valor_reconocido': int(row.get('valor_reconocido', 0)),
                            'dno_hash': str(row.get('dno_hash', '')),
                        }
            except Exception as e:
                print(f"Aviso leyendo Parquet local: {e}")

        # Si no hay Parquet, intentar CSV
        if not processed_records:
            csv_parts = glob.glob(os.path.join(output_gold_dir, "**", "*.csv"), recursive=True)
            for part in csv_parts:
                with open(part, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        processed_records[row['id_solicitud']] = row
        
    if not processed_records:
        raise FileNotFoundError(f"No se encontraron archivos procesados en: {output_gold_dir}")
        
    print(f"Total registros leídos de la capa Gold: {len(processed_records):,}")
    
    # 3. Recorrer el archivo original y contrastar cada decisión frente al oráculo
    total_evaluados = 0
    discrepancias_decision = 0
    discrepancias_porcentaje = 0
    discrepancias_valor = 0
    fugas_pii = 0
    
    with open(input_csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            id_sol = row['id_solicitud']
            if id_sol not in processed_records:
                # Registro no encontrado o en cuarentena
                continue
                
            total_evaluados += 1
            proc = processed_records[id_sol]
            
            # Cálculo oráculo independiente
            glosa = row['glosa']
            # Extracción simple por split
            partes = [p.strip() for p in glosa.split(';') if ':' in p]
            glosa_dict = {}
            for p in partes:
                k, v = p.split(':', 1)
                glosa_dict[k.strip().lower()] = v.strip()
                
            servicio_oracle = glosa_dict.get('serviciosolicitado', '').lower()
            perfil_oracle = glosa_dict.get('perfilcobertura', '').upper()
            valor_proc = int(row['valor_procedimiento'])
            
            cubre_oracle = servicio_oracle in servicios_set
            pct_oracle = perfiles_map.get(perfil_oracle, 0) if cubre_oracle else 0
            val_oracle = _round_half_up(valor_proc * (pct_oracle / 100.0))
            decision_oracle = "CUBRE" if cubre_oracle else "NO CUBRE"
            
            # Comparaciones exactas
            if proc['decision'] != decision_oracle:
                discrepancias_decision += 1
            if int(proc['porcentaje_cobertura']) != pct_oracle:
                discrepancias_porcentaje += 1
            if int(proc['valor_reconocido']) != val_oracle:
                discrepancias_valor += 1
                
            # Verificación de privacidad: los campos de hash deben ser de 64 chars y no contener el DNO real
            dno_real = glosa_dict.get('dno', '')
            dno_hash = str(proc.get('dno_hash', ''))
            if len(dno_hash) != 64 or (dno_real and dno_real in dno_hash):
                fugas_pii += 1
                
    exactitud_decision = ((total_evaluados - discrepancias_decision) / total_evaluados * 100) if total_evaluados > 0 else 0
    exactitud_valor = ((total_evaluados - discrepancias_valor) / total_evaluados * 100) if total_evaluados > 0 else 0
    
    elapsed = time.time() - t0
    
    results = {
        "tiempo_validacion_segundos": round(elapsed, 2),
        "total_registros_evaluados": total_evaluados,
        "discrepancias_decision": discrepancias_decision,
        "discrepancias_porcentaje": discrepancias_porcentaje,
        "discrepancias_valor": discrepancias_valor,
        "fugas_privacidad_pii": fugas_pii,
        "porcentaje_exactitud_decision": exactitud_decision,
        "porcentaje_exactitud_financiera": exactitud_valor,
        "estado_auditoria": "APROBADO_100_EXACTITUD" if (discrepancias_decision == 0 and discrepancias_valor == 0 and fugas_pii == 0) else "RECHAZADO"
    }
    
    print("\n---------------- RESULTADOS DEL ORÁCULO ----------------")
    print(f"Total registros auditados: {total_evaluados:,}")
    print(f"Exactitud de Decisión: {exactitud_decision:.2f}% (Discrepancias: {discrepancias_decision})")
    print(f"Exactitud Financiera: {exactitud_valor:.2f}% (Discrepancias: {discrepancias_valor})")
    print(f"Fugas de PII detectadas: {fugas_pii}")
    print(f"Estado de Auditoría: {results['estado_auditoria']}")
    print(f"Tiempo de validación: {elapsed:.2f} s")
    print("--------------------------------------------------------\n")
    
    return results

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    input_file = os.path.join(base_dir, "dataset", "sample_1000.csv")
    servicios = os.path.join(base_dir, "dataset", "COIL_catalogo_servicios_cubiertos.csv")
    perfiles = os.path.join(base_dir, "dataset", "COIL_catalogo_perfiles_cobertura.csv")
    gold_dir = os.path.join(base_dir, "output", "gold_curated")
    
    run_oracle_validation(input_file, servicios, perfiles, gold_dir)
