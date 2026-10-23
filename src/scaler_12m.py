"""
scaler_12m.py
Generador y escalador sintético para el benchmark de 12 Millones de órdenes médicas.
Multiplica el dataset base de 1.2M x10 garantizando:
- Identificadores únicos correlativos (CHV-12M-00000001 a CHV-12M-12000000)
- Preservación exacta de la distribución estadística de glosas, servicios y perfiles
- Cumplimiento de pruebas de estrés para validar el SLA de < 24h
"""

import os
import sys
import csv
import time

def scale_dataset_to_12m(input_1_2m_path: str, output_12m_path: str, factor: int = 10):
    print("=" * 65)
    print(f"GENERANDO DATASET ESCALADO A {factor * 1.2:.1f} MILLONES DE ÓRDENES MÉDICAS")
    print("=" * 65)
    t0 = time.time()
    
    if not os.path.exists(input_1_2m_path):
        raise FileNotFoundError(f"Archivo base de 1.2M no encontrado: {input_1_2m_path}")
        
    total_written = 0
    
    with open(output_12m_path, 'w', encoding='utf-8', newline='') as fout:
        writer = None
        
        for replica in range(factor):
            print(f"  > Procesando réplica {replica + 1} de {factor}...")
            with open(input_1_2m_path, 'r', encoding='utf-8') as fin:
                reader = csv.DictReader(fin)
                if replica == 0:
                    fieldnames = reader.fieldnames
                    writer = csv.DictWriter(fout, fieldnames=fieldnames)
                    writer.writeheader()
                    
                for row in reader:
                    total_written += 1
                    # Asignar identificador único correlativo
                    row['id_solicitud'] = f"CHV-12M-{total_written:08d}"
                    writer.writerow(row)
                    
            elapsed = time.time() - t0
            print(f"    Progreso: {total_written:,} órdenes generadas ({elapsed:.1f} s)")
            
    total_time = time.time() - t0
    file_size_gb = os.path.getsize(output_12m_path) / (1024**3)
    
    print("\n---------------- GENERACIÓN COMPLETADA ----------------")
    print(f"Total de registros generados: {total_written:,}")
    print(f"Tamaño del archivo resultante: {file_size_gb:.2f} GB")
    print(f"Tiempo total de generación: {total_time:.2f} s ({total_time/60:.2f} min)")
    print(f"Archivo guardado en: {output_12m_path}")
    print("-------------------------------------------------------\n")

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    input_file = os.path.join(base_dir, "dataset", "COIL_dataset_glosas_salud_1_2M.csv")
    output_file = os.path.join(base_dir, "dataset", "COIL_dataset_glosas_salud_12M.csv")
    
    # Puede invocarse con argumentos: python scaler_12m.py [factor]
    factor = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    scale_dataset_to_12m(input_file, output_file, factor)
