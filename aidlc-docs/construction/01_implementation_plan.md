# AI-DLC Construction: Plan de Implementación Modular
**Proyecto:** Solución Distribuida en la Nube para el Procesamiento Masivo de Órdenes Médicas en un Sistema Público de Salud  
**Marco Metodológico:** AWS Labs AI-DLC (`awslabs/aidlc-workflows`) - Fase de Construcción

---

## 1. Unidades de Generación de Código (Code Generation Units)

Siguiendo las directrices estrictas de AI-DLC, el desarrollo se divide en módulos desacoplados y testeables:

| Unidad | Archivo / Componente | Responsabilidad | Criterio de Finalización |
| :--- | :--- | :--- | :--- |
| **CGU-01** | `src/utils/glosa_parser.py` | Extracción de los 7 subcampos de la glosa médica semiestructurada mediante expresiones regulares y hashing SHA-256 para PII (DNO, nombres). | 100% de parseo correcto en glosas válidas; detección precisa de malformaciones. |
| **CGU-02** | `src/utils/rule_engine.py` | Motor de reglas de negocio que cruza el servicio solicitado contra el catálogo oficial de 20 servicios cubiertos y aplica los porcentajes según el perfil (100%, 50%, 25%, 0%). | Cálculo financiero exacto en centavos/enteros COP; generación de alertas de referencia. |
| **CGU-03** | `src/batch_processor.py` | Motor de procesamiento por lotes ejecutable localmente con cero dependencias externas. Genera particiones por fecha, zona de cuarentena y métricas JSON. | Procesamiento de 1.2M en $< 30$ s; conciliación contable sin pérdidas ni duplicados. |
| **CGU-04** | `src/aws_glue_job.py` | Script PySpark para AWS Glue 4.0/5.0. Utiliza optimizaciones Catalyst, joins tipo Broadcast y compresión Parquet Snappy. | Ejecución distribuida elástica en clúster AWS Glue. |
| **CGU-05** | `src/oracle_validator.py` | Oráculo de auditoría independiente que recalcula y contrasta el 100% de las órdenes contra las decisiones tomadas por el procesador. | Exactitud de decisión = 100%; discrepancias financieras = 0; fugas de PII = 0. |
| **CGU-06** | `src/scaler_12m.py` | Generador sintético de pruebas de estrés que escala el dataset de 1.2M a 12M de órdenes médicas con identificadores únicos correlativos. | Generación de 12M registros manteniendo la distribución estadística de perfiles y canales. |
| **CGU-07** | `infrastructure/cloudformation_template.yaml` | Plantilla de Infraestructura como Código (IaC) para desplegar S3, Glue Database, Glue Job, Athena y roles IAM compatibles con LabRole. | Despliegue automatizado reproducible en AWS Academy Learner Lab. |
| **CGU-08** | `infrastructure/athena_ddl.sql` | Definición de esquemas externos y vistas analíticas optimizadas para auditoría y tableros de control. | Tablas y vistas creadas y consultables en Athena. |

---

## 2. Convenciones de Código y Estándares de Seguridad

1. **Codificación:** UTF-8 estricto en todos los módulos para preservar tildes, caracteres especiales y nombres en español sin corrupción.
2. **Tipado Estático:** Anotaciones de tipos (`typing.Dict`, `Tuple`, `Optional`) en funciones críticas para facilitar mantenimiento y análisis estático.
3. **Manejo de Errores y Cuarentena:** Ningún fallo individual de una glosa debe arrojar una excepción no capturada que interrumpa el job distribuido. Todo fallo se desvía a la partición de cuarentena.
4. **Protección de Datos Personales (Ley 1581 de 2012):** Nunca se almacenan ni exponen identificadores de pacientes en claro en la capa analítica Gold. Se utiliza `hashlib.sha256` en Python y `F.sha2(col, 256)` en Spark.
