# Plan de proyecto — DocuProcess Cloud

Proyecto final de *Infraestructura III*, Universidad ICESI.
Equipo: **Juan José De La Pava** y **Diego Polanco**.

Este plan define qué entrega el proyecto, qué deja por fuera, cuándo se construyó cada parte y qué recursos necesita para funcionar. Los identificadores de requisitos remiten a `specs/`; las decisiones, a `specs/adr/`.

## 1. Contexto

DocuProcess Cloud es una plataforma SaaS para el procesamiento asíncrono de recibos y facturas. Los usuarios empresariales se registran, inician sesión, suben un PDF de una página o una imagen PNG/JPEG y consultan en el navegador el resultado extraído (comercio, fechas, totales, moneda). Cuando el procesamiento termina, reciben un correo.

La infraestructura corre en el AWS Academy Sandbox (Vocareum), región `us-east-1`. El sandbox no permite crear roles de IAM, no tiene Lambda, solo admite RDS Single-AZ y limita los tipos de instancia y de volumen. Todas las decisiones de este plan respetan esos límites (`specs/02-aws-sandbox-constraints.md`).

## 2. Objetivos

| # | Objetivo | Cómo se mide |
|---|---|---|
| O1 | Desplegar toda la plataforma desde un sandbox vacío con Infraestructura como Código y un solo comando | `make up VERSION=1.0.0` termina con los targets sanos y la URL de CloudFront, sin pasos manuales en la consola salvo confirmar los correos de SNS (`TST-E2E-03`) |
| O2 | Procesar documentos de forma asíncrona, desacoplada de la petición web | La subida responde `202`; el worker lleva el job a un estado terminal en menos de 2 minutos (`WRK-ACC-02`) |
| O3 | Guardar cada tipo de dato en el almacén que mejor le sirve | Usuarios y sesiones en RDS MySQL; documentos, jobs y resultados en DynamoDB (`docs/data-justification.md`) |
| O4 | Escalar la capa de aplicación con la carga y sobrevivir a la pérdida de una instancia | Auto Scaling Group con mínimo 2 y máximo 4, target tracking al 60 % de CPU (`INF-ASG-*`) |
| O5 | Notificar a usuarios y operadores | Correo por SNS en cada estado terminal de un job y en cada alarma de CloudWatch (`WRK-NOT-*`, `OBS-ALM-*`) |
| O6 | Mantener el sistema privado y auditable | Instancias y base de datos en subredes privadas, sin SSH, acceso por SSM Session Manager, historial de eventos de CloudTrail (`SEC-*`, `INF-AUD-*`) |

## 3. Alcance

### Incluido

- **Portal web** (HTML/CSS/JS estático en S3 + CloudFront): registro, inicio de sesión, subida, historial y detalle de documentos.
- **API REST** (Python 3.12, FastAPI) en EC2: autenticación, sesiones, roles, subida y consulta de estado y resultados.
- **Worker** en las mismas instancias EC2: toma jobs de DynamoDB con leases, descarga el archivo de S3, ejecuta el motor de extracción, guarda el resultado y publica en SNS.
- **Motor de extracción de recibos**: biblioteca Python pura con OCR local (Tesseract) y sin dependencia de AWS (`ADR-011`, `ADR-012`).
- **Infraestructura como Código**: raíz de Terraform con 12 módulos; los buckets de S3 son un stack de CloudFormation gestionado por Terraform (`ADR-035`).
- **Configuración de instancias**: script `userData` que instala Tesseract, descarga la versión desde S3, verifica TLS con MySQL, ejecuta las migraciones y arranca los servicios de systemd (`infra/terraform/templates/userdata.sh.tftpl`).
- **Scripts de operación**: empaquetado, publicación, despliegue del frontend, reconciliación del estado tras un reset del lab, espera de salud, prueba de humo y prueba de carga (`scripts/`).
- **Monitoreo**: siete alarmas de CloudWatch (CPU alta del ASG, pocas instancias en servicio, hosts no sanos en el ALB, errores 5xx del ALB, CPU de RDS, almacenamiento libre de RDS, conexiones de RDS) y un dashboard.
- **Documentación y presentación** (esta carpeta y `docs/`).

### Fuera de alcance

- Dominios y certificados propios (el registro en Route 53 no está disponible; se usan los nombres por defecto de CloudFront y del ALB).
- RDS Multi-AZ y un segundo NAT gateway (límite del sandbox y costo; riesgos aceptados en `ADR-003` y `ADR-005`).
- Lambda, SQS y Textract (no disponibles para el rol de la instancia; `ADR-023`, `ADR-010`, `ADR-012`).
- Documentos de varias páginas, archivos de más de 5 MiB y extracción estructurada de ítems (`ADR-013`, `ADR-029`).
- Recibos reales o datos personales. Todas las muestras de `samples/` son sintéticas.
- Limitación de intentos de inicio de sesión y carga de nivel productivo (ver riesgo R5).

## 4. Entregables

| Ítem del enunciado | Dónde está |
|---|---|
| Plan de proyecto | `entrega_proyecto_final/project-plan.md` (este archivo) |
| Plantillas de IaC (Terraform + CloudFormation) | `infra/terraform/`: módulo raíz y `modules/`. La plantilla de CloudFormation de los buckets es `infra/terraform/modules/buckets/templates/buckets.yaml` |
| Scripts de configuración | `infra/terraform/templates/userdata.sh.tftpl` (arranque de instancias) y `scripts/` |
| Código de la aplicación | `app/api`, `app/worker`, `app/receipt_engine`, `app/frontend` |
| Documentación | `entrega_proyecto_final/documentation.md`, con el detalle en `docs/` |
| Presentación | `entrega_proyecto_final/presentation.pdf` |
| Demostración en vivo | Guion en `docs/demo-script.md` |

## 5. Cronograma

Las fechas salen del historial de Git del repositorio.

| Fase | Fechas | Trabajo | Resultado |
|---|---|---|---|
| 1. Requisitos y diseño | 2026-11-03 | Traducir el enunciado a especificaciones, registrar las restricciones del sandbox, escribir los primeros ADR y los documentos de arquitectura, datos y despliegue | `specs/`, `specs/adr/`, `docs/` |
| 2. Infraestructura como Código | 2026-11-03 | Módulos de Terraform para red, seguridad, ALB, cómputo, base de datos, DynamoDB, buckets (CloudFormation), frontend, mensajería, monitoreo y auditoría | `infra/terraform/`, `make tf-validate` pasa |
| 3. Aplicación | 2026-11-08 | Motor de extracción, API, worker, demo local con AWS simulado y Tesseract real; pruebas de contrato y golden | `app/`, `make test` pasa |
| 4. Frontend y primer despliegue | 2026-11-10 | Espacio de trabajo del portal; cambio a la AMI de Ubuntu por Tesseract y eliminación del instance refresh tras denegaciones del sandbox; página visual de arquitectura | Primer despliegue real, `ADR-038`, `ADR-039` |
| 5. Operación y escalado | 2026-11-10 a 2026-11-11 | Despliegue con un comando, prueba de carga, reconciliación del estado tras un reset del lab; escalado observado de 2 a 3 instancias | `make up`, `make load`, `ADR-040` |
| 6. Entrega y sustentación | 2026-11-13 | Plan de proyecto, guía de documentación y presentación; despliegue en vivo desde un sandbox limpio, flujo completo y prueba de carga | `entrega_proyecto_final/`, evaluación con la rúbrica |

## 6. Recursos

### Personas

- Juan José De La Pava
- Diego Polanco

Ambos trabajan con el mismo proceso guiado por especificaciones definido en `AGENTS.md`; los agentes de IA de programación siguen las mismas reglas.

### Herramientas

| Herramienta | Uso |
|---|---|
| Terraform ≥ 1.6, proveedor de AWS (fijado en `.terraform.lock.hcl`) | Infraestructura como Código |
| AWS CloudFormation | Stack de buckets, creado y destruido por Terraform |
| Python 3.12, uv, FastAPI, pytest, ruff, mypy | Aplicación, pruebas, lint |
| Tesseract OCR (español e inglés) | Extracción de texto, en local y en las instancias |
| AWS CLI, plugin de Session Manager | Verificaciones del sandbox y acceso a las instancias |
| Git, Make | Control de versiones y punto de entrada único de comandos |
| Ubuntu 24.04 (WSL) | Estación de desarrollo y de operación |

### Recursos de AWS (por despliegue)

| Servicio | Configuración |
|---|---|
| VPC | `10.0.0.0/16`, 2 subredes públicas, 2 privadas de aplicación y 2 privadas de base de datos en dos AZ; Internet gateway, 1 NAT gateway, endpoints de gateway para S3 y DynamoDB |
| EC2 + Auto Scaling | `t3.micro`, Ubuntu 24.04, volumen raíz gp2, mínimo 2 / máximo 4, target tracking al 60 % de CPU |
| Application Load Balancer | Público, HTTP :80, health check `/api/v1/health` en el puerto 8000 |
| CloudFront | Punto de entrada HTTPS; origen S3 con OAC para el portal, origen ALB para `/api/*` |
| S3 | Buckets de frontend, archivos subidos, artefactos de versión y logs de auditoría |
| RDS | MySQL 8.0, `db.t3.micro`, Single-AZ, gp2, privado |
| DynamoDB | Tablas `documents` y `jobs`, bajo demanda |
| SNS | Tópicos `processing-events` y `ops-alarms` con suscripciones por correo |
| CloudWatch | Siete alarmas y un dashboard |
| Systems Manager | Acceso por Session Manager; contraseña de la base de datos en Parameter Store |
| IAM | Solo el instance profile preexistente del lab; Terraform no crea ningún recurso de IAM |

### Presupuesto

El sandbox aporta el crédito de AWS; el proyecto no paga nada por fuera de él. Para cuidar el crédito, el stack usa los tamaños más pequeños permitidos, un solo NAT gateway y DynamoDB bajo demanda, y se destruye con `make destroy` al final de cada sesión de trabajo.

## 7. Riesgos

| ID | Riesgo | Efecto | Respuesta |
|---|---|---|---|
| R1 | La sesión del lab expira a las 2 horas aproximadamente; un reset del lab borra casi todos los recursos, pero no todos | Despliegues que fallan a mitad de camino; el estado de Terraform deja de coincidir con AWS | `make prepare-state` reconcilia el estado antes de cada `make up` (`ADR-040`) |
| R2 | El sandbox niega una acción que el diseño necesita | Despliegue bloqueado | Probar temprano con verificaciones de solo lectura y dry-run; registrar cada respuesta (`specs/answered-questions.md`) y adaptar el diseño con un ADR |
| R3 | Un solo NAT gateway y RDS Single-AZ | La caída de una zona detiene el procesamiento o los inicios de sesión | Aceptado para el sandbox (`ADR-003`, `ADR-005`) |
| R4 | El escalado es lento porque el monitoreo detallado está denegado | En la demo hay que esperar de 8 a 12 minutos por una instancia nueva | Arrancar la prueba de carga temprano en la demo |
| R5 | Una avalancha de inicios de sesión agota la memoria de la `t3.micro` (Argon2id usa 64 MiB por verificación) | La API se reinicia y el ALB responde 502 | La prueba de carga mantiene la concurrencia en 4 clientes; la limitación de intentos queda fuera de alcance |
| R6 | La creación de un trail de CloudTrail está denegada | No hay trail propio del proyecto | Usar el historial de eventos de CloudTrail; documentado como `INF-AUD-03` |
| R7 | No se puede leer el límite de 9 instancias de la cuenta | `max_size = 4` podría no caber | Plan B: bajar `asg_max_size` a 3 (`Q-006`) |
