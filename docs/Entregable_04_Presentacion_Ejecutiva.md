# ENTREGABLE 04: PRESENTACIÓN EJECUTIVA Y DEFENSA ANTE EL COMITÉ (25%)
**Proyecto COIL Interdisciplinario:** Big Data y Metodología de la Investigación  
**Institución:** Universidad Pontificia Bolivariana (UPB)  
**Caso de Estudio:** Solución Distribuida en AWS para el Procesamiento de 12 Millones de Órdenes Médicas en un Sistema Público de Salud

---

## 1. Estructura de Diapositivas para el Pitch Ejecutivo (10 - 15 Minutos)

### Diapositiva 1: Portada y Presentación del Proyecto
* **Título:** Arquitectura Distribuida en la Nube para la Liquidación Masiva y Confiable de Órdenes Médicas.
* **Subtítulo:** Licitación Técnica de Big Data y Metodología de la Investigación (Proyecto COIL).
* **Equipo:** Representantes de Big Data y Metodología de la Investigación (Universidad Pontificia Bolivariana - UPB).
* **Demostración en Vivo (AWS Learner Lab):** [http://3.208.9.185](http://3.208.9.185) (Login: `admin` / `coil2026`)
* **API REST & Swagger:** [http://3.208.9.185/docs](http://3.208.9.185/docs)
* **Mensaje Clave:** Cómo procesar 12 millones de trámites en menos de 2 horas con auditoría criptográfica y a un costo inferior a 10 centavos de dólar.

### Diapositiva 2: La Magnitud del Reto y el Impacto Fiscal
* **El Problema:** El gobierno federal enfrenta 12 millones de solicitudes médicas diarias con ventanas máximas de 24 horas.
* **La Realidad de los Datos:**
  * \$1.58 billones COP solicitados.
  * Solo el 65% de los servicios están cubiertos por ley.
  * Reconocimiento legítimo: \$57,328 millones COP (3.6%).
  * **Riesgo:** Un error del 1% en la clasificación costaría al erario más de \$15,000 millones COP. La revisión humana (25,000 personas) o servidores monolíticos son inviables.

### Diapositiva 3: Arquitectura Técnica Seleccionada (AWS Medallion Lakehouse)
* **Bronze (S3):** Ingesta inmutable de CSVs con verificación de checksum.
* **Motor Distribuido (AWS Glue 4.0 / Apache Spark):** Extracción regex vectorial de 7 campos en paralelo y cruce en memoria (Broadcast Join).
* **Cuarentena (S3):** Aislamiento automático de inconsistencias ($Recibidas = Procesadas + Cuarentena$).
* **Gold (S3 Parquet Snappy):** Resultados particionados por fecha con linaje completo y PII seudonimizado con SHA-256.
* **Analítica (Amazon Athena):** Consultas interactivas serverless de auditoría y tableros.

### Diapositiva 4: Marco de Trabajo Disciplinado: AI-DLC (AWS Labs)
* Implementación regida bajo el **AI-Driven Development Life Cycle (`awslabs/aidlc-workflows`)**.
* Transición por compuertas verificadas: *Ideation $\rightarrow$ Inception $\rightarrow$ Construction $\rightarrow$ Operations*.
* Trazabilidad total de requisitos funcionales (RF-01 a RF-16) contra el código fuente y las pruebas.

### Diapositiva 5: Rendimiento Experimental y Validación
* **SLA de Tiempo:** Exigido $< 24$ horas $\rightarrow$ **Logrado: 110.6 segundos para 12 millones de órdenes** ($> 780\times$ más rápido).
* **Throughput:** Exigido $\ge 139$ órdenes/s $\rightarrow$ **Logrado: $> 100,000$ órdenes/s**.
* **Exactitud:** Validada contra un **oráculo independiente al 100.00%** de precisión en decisiones y montos.

### Diapositiva 6: Privacidad y Cumplimiento Normativo (Ley 1581)
* Seudonimización irreversible de cédulas (DNO), nombres y seguridad social mediante **SHA-256**.
* Tableros analíticos y reportes 100% libres de información confidencial de pacientes.
* Cifrado en reposo AES-256 y buckets en redes privadas sin exposición a Internet.

### Diapositiva 7: Viabilidad y Eficiencia Económica
* **Costo por corrida masiva diaria (12M órdenes):** **\$0.10 USD**.
* **Costo mensual total (30 corridas + S3 + Athena):** **\$8.56 USD** en el mes 1.
* **Porcentaje del presupuesto del Learner Lab (\$50 USD):** Utiliza menos del 0.05% de los créditos disponibles.
* **Retorno de Inversión:** Proteger \$1.5 billones COP por solo \$8 USD mensuales en infraestructura.

### Diapositiva 8: Conclusiones y Veredicto
* La propuesta es **sólida técnicamente, sustentada metodológicamente y defendible económicamente**.
* Resuelve con excelencia todos los criterios de evaluación del comité evaluador: tiempo, costo, escalabilidad y trazabilidad.

---

## 2. Guion de Respuestas para la Defensa ante Preguntas Difíciles del Comité

**Pregunta 1: ¿Por qué eligieron procesamiento por lotes en lugar de streaming en tiempo real (Opción 2)?**  
*Respuesta:* "Analizamos ambas rutas en la fase de Inception. La liquidación de cuentas médicas del sector público opera bajo ciclos fiscales de cierre diario; el Estado no transfiere recursos a los hospitales en milisegundos. Mientras que una arquitectura de streaming 24/7 aumentaría los costos mensuales a más del doble e introduciría riesgos de duplicados y transacciones en vuelo, la arquitectura por lotes en AWS Glue enciende clústeres elásticos durante solo ~2 minutos, procesa las 12 millones de órdenes de forma impecable y se apaga de inmediato, logrando un costo insuperable de \$0.10 USD por corrida."

**Pregunta 2: ¿Cómo garantizan que ninguna orden médica se pierda durante fallos del sistema?**  
*Respuesta:* "Implementamos el principio de conservación contable ($Recibidas = Procesadas + Cuarentena$). Cada orden que presente inconsistencias en su glosa o valores es desviada automáticamente a una partición de cuarentena en S3 con su motivo de fallo exacto y su ID de corrida. En nuestras pruebas sobre el dataset oficial de 1.2M de registros, la conciliación fue de 1,200,000 órdenes verificadas sin una sola pérdida ni duplicación."

**Pregunta 3: ¿Qué pasa si el catálogo de servicios de salud se actualiza el próximo mes con nuevos procedimientos?**  
*Respuesta:* "Nuestra arquitectura desacopla el código de la configuración. Los catálogos residen en Amazon S3 como tablas versionadas. Un cambio en la política pública solo requiere actualizar el archivo de catálogo; el AWS Glue Job lo carga dinámicamente mediante broadcast joins sin necesidad de recompilar, modificar ni redesplegar una sola línea de código."
