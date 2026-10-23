# AI-DLC Inception: Diseño Técnico y Arquitectura Distribuida en AWS
**Proyecto:** Solución Distribuida en la Nube para el Procesamiento Masivo de Órdenes Médicas en un Sistema Público de Salud  
**Marco Metodológico:** AWS Labs AI-DLC (`awslabs/aidlc-workflows`) - Componente de Arquitectura

---

## 1. Visión General de la Arquitectura

Para procesar **12 millones de órdenes médicas** garantizando trazabilidad, exactitud del 100%, cumplimiento de la Ley 1581 (privacidad) y un costo operativo mínimo, se adopta una **Arquitectura de Lago de Datos por Capas (Medallion Lakehouse) sobre AWS**.

### Diagrama de Arquitectura en la Nube de AWS

```mermaid
flowchart TD
    subgraph Fuentes ["1. Fuentes de Datos (10 Entidades / 7 Canales)"]
        F1["Portal Ciudadano"]
        F2["Hospitales Públicos"]
        F3["Clínicas Aliadas"]
        F4["Farmacias / Ventanillas"]
    end

    subgraph Ingestion ["2. Ingesta y Almacenamiento Crudo"]
        S3Raw["Amazon S3 - Capa Bronze\n(Archivos CSV Crudos Inmutables\nChecksum SHA-256)"]
        S3Cat["Amazon S3 - Catálogos Versionados\n(Servicios Cubiertos & Perfiles)"]
    end

    subgraph Processing ["3. Motor de Procesamiento Distribuido"]
        GlueJob["AWS Glue 4.0 Job / Apache Spark 3.3+\n(2 a 10 DPUs G.1X elásticos)\n- Parseo Regex de Glosa (7 campos)\n- Broadcast Join de Catálogos\n- Motor de Reglas & Liquidación\n- Seudonimización SHA-256 PII\n- Enrutamiento a Cuarentena"]
    end

    subgraph Storage ["4. Almacenamiento Curado & Auditoría"]
        S3Gold["Amazon S3 - Capa Gold Curada\n(Formato Parquet Snappy Columnar\nParticionado por fecha_particion)"]
        S3Quarantine["Amazon S3 - Capa Cuarentena\n(CSV con Motivo de Rechazo)"]
    end

    subgraph Consumption ["5. Capa de Consulta, Analítica y Auditoría"]
        Athena["Amazon Athena (Motor Serverless Presto/Trino)\nConsultas SQL Interactivas"]
        CloudWatch["Amazon CloudWatch\n(Métricas de Rendimiento, Duración y Logs)"]
        Dashboards["Tableros de Decisión y Control\n(Auditoría Gubernamental, Gasto Público)"]
    end

    Fuentes -->|Carga Diaria / Batch| S3Raw
    S3Raw --> GlueJob
    S3Cat -->|Broadcast In-Memory| GlueJob
    GlueJob -->|Órdenes Válidas Liquidadas| S3Gold
    GlueJob -->|Órdenes Defectuosas / Rechazadas| S3Quarantine
    GlueJob -.->|Métricas & Alertas| CloudWatch
    S3Gold --> Athena
    S3Quarantine --> Athena
    Athena --> Dashboards
```

---

## 2. Flujo de Datos por Capas (Medallion Architecture)

```mermaid
flowchart LR
    A["Bronze (Raw)\nCSV original\nInmutable"] -->|Validación Esquema| B{"¿Es válida la Glosa y Valor?"}
    B -- No --> C["Cuarentena (S3)\nMotivo del fallo\nAuditoría"]
    B -- Sí --> D["Silver (Clean)\n7 subcampos atómicos\nNormalización texto"]
    D --> E["Cálculo Cobertura\nBroadcast Join\nPrioritario 100%\nEstándar 50%\nCopago 25%"]
    E --> F["Gold (Curated)\nParquet Snappy\nPartición fecha\nPII Seudonimizado (SHA-256)\nLinaje completo"]
```

1. **Capa Bronze (`s3://.../bronze/`):**
   * Almacena los archivos CSV tal como son emitidos por los canales y entidades.
   * Totalmente inmutable. Se registra hash SHA-256 de entrada para garantizar que la fuente nunca fue alterada.
2. **Capa de Cuarentena (`s3://.../quarantine/`):**
   * Registros que presenten malformaciones en la glosa (claves faltantes, errores de sintaxis) o valores negativos/no numéricos.
   * Cada registro en cuarentena almacena: `id_solicitud`, `glosa_raw`, `motivo_rechazo`, `id_corrida` y `timestamp_rechazo`.
   * Permite cumplir la ecuación contable:
     $$\text{Total Recibidas} = \text{Total Procesadas en Gold} + \text{Total en Cuarentena}$$
3. **Capa Gold Curada (`s3://.../gold/curated_solicitudes/`):**
   * Almacenamiento en formato **Apache Parquet**, comprimido con **Snappy**.
   * Particionado físico por fecha de solicitud (`fecha_particion=YYYY-MM-DD`), reduciendo drásticamente los datos escaneados en consultas SQL posteriores.
   * **Privacidad garantizada:** Los identificadores directos (`dno`, `seguro_social`, `paciente`) se sustituyen por sus respectivos hashes seudonimizados SHA-256 (`dno_hash`, `seguro_social_hash`, `paciente_hash`).
   * **Trazabilidad:** Cada registro incorpora `id_corrida`, `version_catalogo`, `regla_aplicada` y `timestamp_procesamiento`.

---

## 3. Justificación y Análisis de Trade-Off: Opción 1 (Lotes) vs. Opción 2 (Híbrida/Streaming)

| Criterio | Opción 1: Procesamiento por Lotes (AWS Glue / Spark) | Opción 2: Ingesta Continua e Híbrida (Kinesis/Firehose + Glue) | Decisión del Proyecto |
| :--- | :--- | :--- | :--- |
| **Tiempo de Corrida** | Procesa los 12 millones en **menos de 2 horas** (piloto en ~2 minutos). | Procesa evento a evento durante el día; latencia de segundos/minutos. | **Opción 1** cumple con creces el SLA de $< 24$ horas. |
| **Costo Operativo** | ~**\$0.10 USD por corrida diaria** de 12M órdenes (~\$8.56 USD/mes). | ~**\$11.57 a \$23.92 USD/mes** (costos continuos de shards/ingesta). | **Opción 1** es hasta **60% más económica** y se adapta perfecto al límite de \$50 USD del Learner Lab. |
| **Complejidad de Infraestructura** | Baja: Clúster efímero/serverless que se enciende, procesa y se destruye automáticamente. | Alta: Demanda streaming activo 24/7, control de duplicados en streaming, buffers y dead-letter queues. | **Opción 1** minimiza riesgos de mantenimiento y sobrecostos por recursos desatendidos. |
| **Requerimiento del Negocio** | El gobierno federal liquida al cierre diario de jornada fiscal. | No se requiere aprobación médica en tiempo real para el pago estatal. | **Opción 1** se alinea exactamente con la operación pública fiscal. |

**Veredicto:** Se selecciona la **Opción 1 (Procesamiento por Lotes con AWS Glue Spark)** como la arquitectura principal del proyecto, dejando la arquitectura híbrida documentada como una extensión futura para casos de uso de preautorizaciones en línea.

---

## 4. Diagrama de Secuencia de la Corrida Diaria

```mermaid
sequenceDiagram
    autonumber
    actor Operador as Operador / Scheduler
    participant S3 as Amazon S3 (Bronze)
    participant Glue as AWS Glue Spark Job
    participant Cat as Catálogos S3
    participant Gold as Amazon S3 (Gold Parquet)
    participant Quar as Amazon S3 (Cuarentena)
    participant Athena as Amazon Athena

    Operador->>Glue: Iniciar Job (args: bucket, prefixes, run_id)
    Glue->>S3: Leer CSV crudo masivo (12M registros)
    Glue->>Cat: Cargar catálogos (Servicios y Perfiles) en memoria Broadcast
    loop Por cada partición Spark
        Glue->>Glue: Parsear glosa con Regex (7 subcampos)
        alt Formato Inválido
            Glue->>Quar: Escribir a cuarentena con motivo
        else Formato Válido
            Glue->>Glue: Cruzar con Catálogo Cubierto (Broadcast)
            Glue->>Glue: Liquidar cobertura (Prioritario 100%, Estándar 50%, Copago 25%, No Cubre 0%)
            Glue->>Glue: Seudonimizar PII con SHA-256
            Glue->>Gold: Escribir registro particionado por fecha (Parquet Snappy)
        end
    end
    Glue->>Operador: Notificar fin de corrida + Métricas CloudWatch
    Operador->>Athena: Ejecutar queries de auditoría y conciliación
    Athena->>Operador: Reporte de conciliación cuadrada (Recibidas = Procesadas + Cuarentena)
```
