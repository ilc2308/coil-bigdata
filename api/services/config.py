"""
services/config.py
Configuración centralizada desde variables de entorno (.env).
Usamos pydantic-settings para carga automática y validación.
"""

from __future__ import annotations
import os
from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


# Directorio raíz del proyecto (dos niveles arriba de api/services/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """
    Configuración de la aplicación COIL.
    Los valores se cargan desde variables de entorno o desde .env.
    """
    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Modo de operación ---
    app_mode: str = "local"   # "local" | "aws"

    # --- Autenticación ---
    app_username: str = "admin"
    app_password: str = "coil2026"
    jwt_secret_key: str = "cambia_esta_clave_secreta_en_produccion"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    # --- Rutas locales ---
    local_base_dir: str = str(_PROJECT_ROOT)
    local_catalogo_servicios: str = "dataset/COIL_catalogo_servicios_cubiertos.csv"
    local_catalogo_perfiles: str = "dataset/COIL_catalogo_perfiles_cobertura.csv"
    local_output_dir: str = "output"
    local_upload_dir: str = "uploads"

    # --- AWS ---
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_session_token: str = ""
    aws_default_region: str = "us-east-1"
    s3_bucket_name: str = ""
    s3_bronze_prefix: str = "bronze/solicitudes/"
    s3_gold_prefix: str = "gold/curated_solicitudes/"
    s3_quarantine_prefix: str = "quarantine/solicitudes/"
    s3_catalogs_prefix: str = "catalogs/"
    s3_athena_results_prefix: str = "athena-results/"
    glue_job_name: str = "coil-bigdata-salud-spark-batch-processor"
    athena_workgroup: str = "coil-bigdata-salud-analytics-wg"
    athena_database: str = "coil_bigdata_salud_db"

    # --- API ---
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # --- Versión del catálogo ---
    version_catalogo: str = "2026.1"

    # --- Propiedades derivadas ---
    @property
    def base_dir(self) -> Path:
        if self.local_base_dir:
            return Path(self.local_base_dir)
        return _PROJECT_ROOT

    @property
    def catalogo_servicios_path(self) -> str:
        return str(self.base_dir / self.local_catalogo_servicios)

    @property
    def catalogo_perfiles_path(self) -> str:
        return str(self.base_dir / self.local_catalogo_perfiles)

    @property
    def output_dir(self) -> str:
        return str(self.base_dir / self.local_output_dir)

    @property
    def upload_dir(self) -> str:
        p = self.base_dir / self.local_upload_dir
        p.mkdir(parents=True, exist_ok=True)
        return str(p)

    @property
    def is_local(self) -> bool:
        return self.app_mode.lower() == "local"

    @property
    def is_aws(self) -> bool:
        return self.app_mode.lower() == "aws"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retorna la instancia singleton de configuración."""
    return Settings()
