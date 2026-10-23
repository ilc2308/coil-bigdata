"""
glosa_parser.py
Módulo de extracción y normalización de glosas médicas semiestructuradas
para el Sistema de Salud de Chernovia (Proyecto COIL Big Data).
Cumple con requerimientos RF-04, RF-05 y RNF-09 (Seudonimización Ley 1581).
"""

import re
import hashlib
from typing import Tuple, Dict, Any, Optional

# Patrón regex robusto para extraer los 7 subcampos obligatorios de la glosa
GLOSA_PATTERN = re.compile(
    r'^Paciente:\s*(?P<paciente>[^;]+);\s*'
    r'DNO:\s*(?P<dno>[^;]+);\s*'
    r'SeguroSocial:\s*(?P<seguro_social>[^;]+);\s*'
    r'Edad:\s*(?P<edad>\d+);\s*'
    r'PerfilCobertura:\s*(?P<perfil>[^;]+);\s*'
    r'ServicioSolicitado:\s*(?P<servicio>[^;]+);\s*'
    r'Medicacion:\s*(?P<medicacion>.*)$',
    re.IGNORECASE
)

def hash_sha256(text: str) -> str:
    """Genera hash SHA-256 para seudonimización de datos sensibles (PII)."""
    if not text:
        return ""
    return hashlib.sha256(text.strip().encode('utf-8')).hexdigest()

def parse_glosa(glosa: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Parsea y valida el texto de la glosa.
    
    Retorna:
        (es_valido, diccionario_datos, motivo_error)
    """
    if not glosa or not isinstance(glosa, str):
        return False, None, "Glosa vacía o no es texto"
    
    glosa_clean = glosa.strip()
    match = GLOSA_PATTERN.match(glosa_clean)
    
    if not match:
        # Intento de diagnóstico para motivo de cuarentena
        if "Paciente:" not in glosa_clean:
            return False, None, "Falta clave obligatoria Paciente"
        if "DNO:" not in glosa_clean:
            return False, None, "Falta clave obligatoria DNO"
        if "ServicioSolicitado:" not in glosa_clean:
            return False, None, "Falta clave obligatoria ServicioSolicitado"
        return False, None, "Formato de glosa no cumple estructura esperada de 7 campos"
    
    data = match.groupdict()
    
    # Limpieza y normalización de textos
    paciente_raw = data['paciente'].strip()
    dno_raw = data['dno'].strip()
    seguro_social_raw = data['seguro_social'].strip()
    
    try:
        edad = int(data['edad'].strip())
    except ValueError:
        return False, None, "Edad no es un número entero válido"
    
    perfil = data['perfil'].strip().upper()
    servicio = data['servicio'].strip()
    medicacion_raw = data['medicacion'].strip()
    
    # Lista de medicaciones divididas por '|'
    if medicacion_raw and medicacion_raw.lower() != 'ninguna':
        medicaciones_lista = [m.strip() for m in medicacion_raw.split('|') if m.strip()]
    else:
        medicaciones_lista = []
    
    parsed = {
        "paciente": paciente_raw,
        "paciente_hash": hash_sha256(paciente_raw),
        "dno": dno_raw,
        "dno_hash": hash_sha256(dno_raw),
        "seguro_social": seguro_social_raw,
        "seguro_social_hash": hash_sha256(seguro_social_raw),
        "edad": edad,
        "perfil_cobertura": perfil,
        "servicio_solicitado": servicio,
        "medicacion_raw": medicacion_raw,
        "medicaciones": medicaciones_lista
    }
    
    return True, parsed, None
