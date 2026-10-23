"""
rule_engine.py
Motor de Reglas de Negocio para el cálculo de cobertura de órdenes médicas.
Cumple con requerimientos RF-06, RF-07, RF-08, RF-14, RF-16.
"""

import csv
import os
from typing import Dict, Any, Tuple, Optional, List

class CoverageRuleEngine:
    def __init__(self, catalogo_servicios_path: str, catalogo_perfiles_path: str, version_catalogo: str = "2026.1"):
        self.version_catalogo = version_catalogo
        self.servicios_cubiertos: Dict[str, Dict[str, Any]] = {}
        self.perfiles_cobertura: Dict[str, int] = {}
        
        self._load_catalogo_servicios(catalogo_servicios_path)
        self._load_catalogo_perfiles(catalogo_perfiles_path)

    def _load_catalogo_servicios(self, path: str):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Catálogo de servicios no encontrado en: {path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                servicio_nombre = row['servicio'].strip()
                # Guardamos normalizado en minúsculas y exacto
                meds_ref = [m.strip().lower() for m in row['medicaciones_referencia'].split('|') if m.strip()]
                self.servicios_cubiertos[servicio_nombre.lower()] = {
                    "codigo_servicio": row['codigo_servicio'].strip(),
                    "servicio_oficial": servicio_nombre,
                    "categoria": row['categoria'].strip(),
                    "medicaciones_referencia": meds_ref,
                    "valor_min_referencia": int(row['valor_min_referencia']),
                    "valor_max_referencia": int(row['valor_max_referencia']),
                    "cubre_sistema_publico": row['cubre_sistema_publico'].strip().upper() == "SI"
                }

    def _load_catalogo_perfiles(self, path: str):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Catálogo de perfiles no encontrado en: {path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                perfil = row['perfil_cobertura'].strip().upper()
                pct = int(row['porcentaje_cobertura_si_el_servicio_esta_cubierto'])
                self.perfiles_cobertura[perfil] = pct

    def evaluate_order(self, servicio_solicitado: str, perfil_cobertura: str, valor_procedimiento: int, medicaciones: List[str]) -> Dict[str, Any]:
        """
        Evalúa una orden médica y calcula cobertura, porcentaje, valor reconocido y auditoría.
        """
        servicio_key = servicio_solicitado.strip().lower()
        perfil_key = perfil_cobertura.strip().upper()
        
        esta_cubierto = servicio_key in self.servicios_cubiertos
        alertas = []
        
        if esta_cubierto:
            info_servicio = self.servicios_cubiertos[servicio_key]
            porcentaje = self.perfiles_cobertura.get(perfil_key, 0)
            valor_reconocido = int(round(valor_procedimiento * (porcentaje / 100.0)))
            decision = "CUBRE"
            regla = "RN-COV-CATALOGO-V1"
            codigo_servicio = info_servicio["codigo_servicio"]
            categoria = info_servicio["categoria"]
            
            # Verificación de alertas informativas (RF-16)
            if valor_procedimiento < info_servicio["valor_min_referencia"]:
                alertas.append("VALOR_BAJO_RANGO")
            elif valor_procedimiento > info_servicio["valor_max_referencia"]:
                alertas.append("VALOR_SOBRE_RANGO")
                
            # Verificación de medicación
            meds_ref = info_servicio["medicaciones_referencia"]
            if meds_ref and meds_ref != ["ninguna"] and medicaciones:
                meds_solicitadas_lower = [m.lower() for m in medicaciones]
                coincidencias = set(meds_ref).intersection(set(meds_solicitadas_lower))
                if not coincidencias:
                    alertas.append("MEDICACION_NO_CONCUERDA")
        else:
            porcentaje = 0
            valor_reconocido = 0
            decision = "NO CUBRE"
            regla = "RN-NOCOV-EXCLUSION-V1"
            codigo_servicio = "NON-COVERED"
            categoria = "No Cubierto"
            alertas.append("SERVICIO_FUERA_DE_CATALOGO")
            
        return {
            "decision": decision,
            "porcentaje_cobertura": porcentaje,
            "valor_reconocido": valor_reconocido,
            "codigo_servicio": codigo_servicio,
            "categoria_servicio": categoria,
            "regla_aplicada": regla,
            "version_catalogo": self.version_catalogo,
            "alertas": "|".join(alertas) if alertas else "NINGUNA"
        }
