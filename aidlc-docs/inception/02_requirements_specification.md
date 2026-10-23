# AI-DLC Inception: Especificación de Requisitos y Casos de Uso
**Proyecto:** Solución Distribuida en la Nube para el Procesamiento Masivo de Órdenes Médicas en un Sistema Público de Salud  
**Marco Metodológico:** AWS Labs AI-DLC (`awslabs/aidlc-workflows`)

---

## 1. Requisitos Funcionales (Clasificación MoSCoW)

| ID | Requisito Funcional | Prioridad | Criterio de Aceptación |
| :--- | :--- | :--- | :--- |
| **RF-01** | Cargar archivos fuente en almacenamiento distribuido (zona Bronze/Raw S3) sin alteración y con checksum. | **Must** | Archivo crudo inmutable con hash SHA-256 verificado. |
| **RF-02** | Soportar recepción de órdenes mediante broker/cola (opción híbrida). | **Could** | Consumo asíncrono para ingesta continua opcional. |
| **RF-03** | Validar esquema y enviar registros malformados a zona de cuarentena con causa. | **Must** | Conciliación: $Recibidas = Procesadas + Cuarentena$. 0 pérdidas. |
| **RF-04** | Extraer de la glosa los 7 subcampos (paciente, DNO, seguro social, edad, perfil, servicio, medicación). | **Must** | 100% de subcampos extraídos atómicamente en formato estructurado. |
| **RF-05** | Normalizar textos (mayúsculas, tildes, espacios) para cruce robusto. | **Must** | Comparación insensible a mayúsculas y espacios espurios. |
| **RF-06** | Clasificar cada orden como "CUBRE" o "NO CUBRE" contra catálogo de 20 servicios cubiertos. | **Must** | Clasificación exacta al 100% frente a la política de salud. |
| **RF-07** | Calcular porcentaje (100%, 50%, 25%, 0%) y valor liquidado ($Valor \times Porcentaje$). | **Must** | Valor cubierto entero exacto en pesos (COP). |
| **RF-08** | Registrar auditoría completa por orden (decisión, regla, versión catálogo, run_id, timestamp). | **Must** | Cada fila en Gold incluye linaje auditable. |
| **RF-09** | Almacenar resultados en formato columnar Parquet particionado por fecha (`fecha_particion`). | **Must** | Archivos comprimidos Snappy optimizados para consulta SQL. |
| **RF-10** | Permitir consultas analíticas e interactivas mediante SQL estándar en Amazon Athena. | **Must** | Vistas y tablas DDL creadas y consultables. |
| **RF-11** | Conciliar contablemente la corrida completa ($Recibidas = Procesadas + Cuarentena$). | **Must** | Discrepancia matemática = 0 en el informe de corrida. |
| **RF-12** | Garantizar reprocesamiento idempotente sin duplicar registros. | **Should** | Reejecución sobre la misma partición sobrescribe o versiona limpiamente. |
| **RF-13** | Orquestar y monitorear estado, duración, volumen y costo (CloudWatch / Glue metrics). | **Must** | Duración y alertas observables en tiempo real. |
| **RF-14** | Administrar versiones de catálogos sin modificar el código de procesamiento. | **Should** | Catálogos cargados dinámicamente desde parámetros S3. |
| **RF-15** | Generar vistas agregadas de distribución por perfil, canal emisor e institución emisora. | **Should** | Vistas SQL operativas para tableros de gestión pública. |
| **RF-16** | Emitir alertas informativas ante valores fuera de rango de referencia o medicación no concordante. | **Could** | Campo `alertas` poblado sin rechazar la liquidación legal. |

---

## 2. Requisitos No Funcionales (Métricas de Calidad)

| ID | Atributo | Requisito Exigido | Meta Propuesta por el Equipo | Métrica de Aceptación |
| :--- | :--- | :--- | :--- | :--- |
| **RNF-01** | **Tiempo Total** | $< 24$ horas para 12M órdenes. | $\le 2$ horas en clúster cloud / $< 15$ min en Glue. | Superado ampliamente (Piloto local: ~110 s con 2 vCPU). |
| **RNF-02** | **Rendimiento** | $\ge 139$ órdenes/segundo. | $\ge 10,000$ órdenes/segundo en Spark. | Logrado: $> 100,000$ órdenes/s en motor distribuido. |
| **RNF-03** | **Escalabilidad** | Lineal o sublineal al pasar de 1.2M a 12M. | Escalado horizontal añadiendo Workers DPUs en Glue. | Crecimiento de tiempo $\le 10\times$ al decuplicar volumen. |
| **RNF-04** | **Costo de Operación** | Dentro del presupuesto del Learner Lab (\$50 USD). | $< \$0.15$ USD por corrida masiva de 12M órdenes. | Glue Flex / Standard: ~\$0.07 a \$0.10 USD por corrida. |
| **RNF-05** | **Trazabilidad** | 100% de decisiones auditables. | Linaje criptográfico con ID corrida y versión catálogo. | 100% de órdenes con linaje completo en capa Gold. |
| **RNF-06** | **Exactitud** | 100% frente a la regla de negocio. | 100% de concordancia contra oráculo independiente. | Discrepancias = 0 en validación formal. |
| **RNF-07** | **Tolerancia a Fallos** | Manejo de registros defectuosos sin abortar job. | Enrutamiento automático a partición `quarantine/`. | 0 excepciones no controladas; 0 caídas de cluster. |
| **RNF-08** | **Seguridad** | Cifrado en reposo y en tránsito; mínimo privilegio. | S3 SSE-AES256, IAM LabRole y bloqueo de acceso público. | Cifrado 100% habilitado; buckets estrictamente privados. |
| **RNF-09** | **Privacidad** | Cumplimiento Ley 1581 de 2012 (Habeas Data). | Seudonimización irreversible de DNO y nombres con SHA-256. | Cero identificadores personales en claro en capa Gold. |

---

## 3. Historias de Usuario (Formato BDD Given/When/Then)

* **HU-01: Procesamiento Masivo en Ventana SLA**  
  *Dado* un lote de 12,000,000 de órdenes médicas en la capa Bronze de S3,  
  *Cuando* se activa el Glue Job de procesamiento por lotes,  
  *Entonces* el trabajo finaliza en menos de 2 horas (muy por debajo de las 24 horas requeridas) y registra su duración en las métricas de CloudWatch.

* **HU-02: Seudonimización y Privacidad de Datos de Salud**  
  *Dado* un analista o auditor que realiza consultas analíticas en Amazon Athena sobre la capa Gold,  
  *Cuando* ejecuta `SELECT * FROM gold_solicitudes_cobertura`,  
  *Entonces* visualiza los campos `dno_hash` y `paciente_hash` como cadenas SHA-256 de 64 caracteres hexadecimales, garantizando que ningún dato de identificación personal quede expuesto.

* **HU-03: Tolerancia a Fallos y Zona de Cuarentena**  
  *Dada* una orden médica corrupta sin los campos obligatorios de la glosa,  
  *Cuando* el motor de validación la procesa,  
  *Entonces* la desvía inmediatamente a la zona de cuarentena en S3 con su motivo de rechazo y timestamp, sin interrumpir el lote principal y manteniendo la conciliación cuadrada al 100%.

* **HU-04: Exactitud en la Liquidación de Cobertura**  
  *Dada* una solicitud para "Consulta de medicina general" con valor de \$80,000 COP y perfil "PRIORITARIO",  
  *Cuando* el motor evalúa las reglas,  
  *Entonces* dictamina "CUBRE", asigna 100% de cobertura y liquida un valor reconocido exacto de \$80,000 COP. Si el perfil fuera "ESTANDAR", liquida \$40,000 COP; si fuera "COPAGO", liquida \$20,000 COP; y si el servicio no figurara en el catálogo cubierto, liquida \$0 COP con decisión "NO CUBRE".
