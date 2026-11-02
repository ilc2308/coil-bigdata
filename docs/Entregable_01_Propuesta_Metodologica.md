# ENTREGABLE 01: DOCUMENTO DE PROPUESTA METODOLÓGICA Y ESTADO DEL ARTE (25%)
**Proyecto COIL Interdisciplinario:** Big Data y Metodología de la Investigación  
**Institución Participante:** Universidad Pontificia Bolivariana (UPB)  
**Caso de Estudio:** Diseño e implementación de una solución distribuida en la nube para el procesamiento masivo de órdenes médicas en un sistema público de salud (Chernovia)

---

## 1. Planteamiento del Problema

### 1.1 Contexto
Un gobierno federal desea automatizar el análisis de órdenes médicas para decidir la cobertura pública, el porcentaje reconocido y la trazabilidad de cada decisión. Cada orden incluye fecha, glosa, medio emisor, valor del procedimiento y entidad emisora; la glosa concentra la identificación del paciente (nombre, DNO y seguro social), su edad, su perfil de cobertura, el servicio solicitado y la medicación. La solución debe clasificar si el Estado cubre o no la orden y calcular el reconocimiento de 100%, 50% o 25% según el perfil, para 12 millones de órdenes en una ventana máxima de 24 horas. El comité valorará el tiempo total, el costo de operación, la escalabilidad y la trazabilidad.

### 1.2 Descripción del Problema
El proceso tiene cinco etapas: recepción del documento, extracción de la glosa, clasificación (cubre o no cubre), cálculo de cobertura y registro trazable de la decisión. El dataset de prueba (1,2 millones de órdenes de tres días hábiles, ≈ 360 MB) muestra que el 35% de las órdenes solicita servicios fuera del catálogo y que, de $1.58 billones solicitados, solo se reconocerían unos $57,300 millones (3.6%): un error de clasificación tiene un impacto económico alto.

A la escala objetivo, la revisión manual no es viable: si una persona tardara un minuto por orden, 12 millones de órdenes exigirían 200,000 horas de trabajo al día, equivalentes a 25,000 personas en jornadas de 8 horas. Tampoco basta un servidor único sin diseño distribuido, porque no garantiza la ventana de 24 horas, la tolerancia a fallos ni el crecimiento del volumen. Los sistemas existentes revisados en el estado del arte resuelven partes del problema, pero ninguno documenta a la vez la decisión automática de cobertura, la trazabilidad completa y el costo por volumen procesado.

### 1.3 Pregunta de Investigación
¿Qué arquitectura distribuida en la nube permite clasificar la cobertura y calcular el porcentaje reconocido de 12 millones de órdenes médicas en menos de 24 horas, con trazabilidad completa de cada decisión y un costo de operación razonable?

### 1.4 Hipótesis
Una arquitectura de lago de datos en Amazon S3 con procesamiento distribuido en Apache Spark sobre un servicio gestionado de AWS procesa 12 millones de órdenes en dos horas o menos, con 100% de exactitud frente a la regla de negocio y un costo de cómputo inferior a US$1 por corrida.

### 1.5 Justificación
* **Técnica:** El volumen y la ventana exigen almacenamiento y procesamiento distribuidos y elásticos.
* **Económica:** El pago por uso permite que el costo crezca con el volumen procesado y no con capacidad ociosa.
* **Social e Institucional:** Decisiones más rápidas, homogéneas y auditables mejoran la transparencia del gasto público en salud.
* **Académica:** La evidencia empírica de arquitecturas de este tipo en Latinoamérica es escasa.

---

## 2. Estado del Arte y Análisis Comparativo

### Tabla Comparativa de Competidores

| Competidor | Cómo Actúa | Arquitectura | Limitación Documentada |
| :--- | :--- | :--- | :--- |
| **FPS – CMS (EE. UU.)** | Revisa reclamaciones de 3 a 5 días después del envío; alertas por riesgo revisadas por analistas. | Sistema web en centro de datos de contratista; 7 fuentes; 25 modelos (reglas, anomalías, predictivos). | No integrado con pagos; falsos positivos de modelos nacionales. |
| **TMS y NHCX – NHA (India)** | Preautorización y reclamación; adjudicación humana en cadena con plazos automáticos. | Gateway de intercambio con API, mensajes FHIR R4 cifrados y respuestas asíncronas. | Adjudicación manual en TMS; migración a NHCX en curso. |
| **MUV FEV-RIPS – MinSalud (Colombia)** | Valida factura (XML) y RIPS (JSON) y emite el CUV para radicar. | Validador centralizado (SISPRO) con reglas codificadas y API para proveedores. | Valida información de facturación; la auditoría y el pago siguen en cada pagador. |
| **NHIA (Taiwán)** | Big data y monitoreo inteligente detectan reclamaciones anómalas; revisión experta. | Repositorio nacional de pagador único con capa analítica (MediCloud). | Detalle técnico no publicado. |
| **Nube comercial (AWS; Mapfre)** | Validación y fraude en paralelo; puntuación por lotes con ML. | Eventos y serverless; lago de datos Iceberg, Spark, Airflow, grafos. | Requiere adaptar reglas y estándares del sector salud. |

---

## 3. Objetivos del Proyecto

### 3.1 Objetivo General
Diseñar, implementar y evaluar una solución distribuida en AWS que procese 12 millones de órdenes médicas en menos de 24 horas, clasifique su cobertura, calcule el porcentaje reconocido (100%, 50% o 25%) y registre cada decisión de forma trazable, con un costo de operación razonable y justificado.

### 3.2 Objetivos Específicos
* **OE1:** Analizar el estado del arte de los sistemas de validación masiva de reclamaciones en salud para identificar enfoques, arquitecturas y vacíos del mercado.
* **OE2:** Especificar los requisitos funcionales, no funcionales y las historias de usuario a partir del reto y del análisis del dataset.
* **OE3:** Diseñar una arquitectura distribuida (por lotes o híbrida) con su flujo de datos, lógica de clasificación y estrategia de costo.
* **OE4:** Implementar un prototipo funcional en el laboratorio de AWS que procese el dataset de 1,2 millones de órdenes y su escalamiento a 12 millones.
* **OE5:** Evaluar el prototipo según tiempo total, rendimiento, exactitud, trazabilidad, escalabilidad y costo, y compararlo con las metas definidas.

---

## 4. Metodología de Investigación y Marco de Trabajo

### 4.1 Enfoque de Investigación
Se sigue la metodología de **Ciencia del Diseño (*Design Science Research*)** (Hevner et al., 2004), orientada a la creación y evaluación rigurosa de artefactos tecnológicos que resuelven problemas del mundo real.

### 4.2 Marco Ágil COIL e Integración con AI-DLC
* **Scrum Adaptado:** Sprints semanales coordinados entre las sedes de Colombia y México con registro en bitácora de decisiones de arquitectura (ADR).
* **AI-DLC (AWS Labs):** Adopción de compuertas formales de verificación (Inception, Construction, Operations) asegurando trazabilidad entre requerimientos y código.

### 4.3 Criterios de Aceptación y Validación Experimental

| Variable | Indicador | Instrumento | Criterio de Éxito |
| :--- | :--- | :--- | :--- |
| **Tiempo Total** | Duración de la corrida completa | Métricas de CloudWatch / Orquestador | $< 24$ h (exigido); $\le 2$ h (meta) |
| **Rendimiento** | Órdenes procesadas por segundo | Órdenes / Duración | $\ge 139$ órdenes/s |
| **Exactitud** | % de decisiones iguales al oráculo | Comparación independiente en Python/SQL | 100% |
| **Trazabilidad** | % de decisiones con linaje completo | Consulta SQL de campos de auditoría | 100% |
| **Escalabilidad** | Comportamiento al pasar de 1.2M a 12M | Pruebas de estrés repetidas | Crecimiento $\le$ lineal |
| **Costo** | USD por corrida y por millón de órdenes | AWS Cost Explorer / Tarificador oficial | $< \$50$ USD (Learner Lab) |
| **Integridad** | $Recibidas = Procesadas + Cuarentena$ | Conciliación matemática | Discrepancia = 0 |

---

## 5. Referencias en Estilo APA

* Casanova, R., Villa-Garzón, F. A., y Branch-Bedoya, J. W. (2025). Architectural patterns for health information systems: A systematic review. *Frontiers in Digital Health*, 7. https://doi.org/10.3389/fdgth.2025.1694839
* Congreso de Colombia. (2012). Ley Estatutaria 1581 de 2012, por la cual se dictan disposiciones generales para la protección de datos personales. *Diario Oficial 48.587*.
* Consultorsalud. (2025, 21 de julio). Minsalud activa actualización 1.4.4 del Mecanismo Único de Validación FEV-RIPS: avances y desafíos para el sistema de salud.
* Government Accountability Office [GAO]. (2012). *Medicare fraud prevention: CMS has implemented a predictive analytics system, but needs to define measures to determine its effectiveness* (GAO-13-104).
* Hevner, A. R., March, S. T., Park, J., y Ram, S. (2004). Design science in information systems research. *MIS Quarterly*, 28(1), 75–105.
* Kuniyil, L., Hausler, D., Urpi Vidal, S., y Solaz Hernandez, V. (2026, 14 de julio). How Mapfre USA modernized fraud claims with Amazon EMR Serverless. *AWS Architecture Blog*.
* Ministerio de Salud y Protección Social. (2024). Resolución 1884 de 2024 (30 de septiembre). *Diario Oficial 52.896*.
* National Health Authority [NHA]. (2023, 14 de noviembre). National Health Authority (NHA) organises Accelerator Workshops on ABDM Integration and NHCX Adoption in association with IRDAI.
* National Health Insurance Administration [NHIA]. (2025). NHIA received the Integrity Award for Excellent Performance in Integrity and Transparency.
* Schwaber, K., y Sutherland, J. (2020). *La Guía Scrum*.
* Shea, E., y Mahapatro, D. (2023, 12 de enero). Building a modern event-driven application for insurance claims processing – Part 1. *AWS for Industries*.
* Taramasco, C., y Rimassa, C. (2023). Architecture assessment of the Chilean epidemiological surveillance system for notifiable diseases (EPIVIGILA): Qualitative study. *JMIR Formative Research*, 7, e34387.
