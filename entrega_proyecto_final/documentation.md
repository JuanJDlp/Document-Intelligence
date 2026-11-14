# Documentación — despliegue y operación de DocuProcess Cloud

Equipo: Juan José De La Pava y Diego Polanco. Infraestructura III, Universidad ICESI.

Esta guía explica cómo desplegar la infraestructura de DocuProcess Cloud en el AWS Academy Sandbox y cómo operarla después. Es el punto de entrada; cada sección enlaza a la referencia detallada.

| Detalle | Documento |
|---|---|
| Diagramas de arquitectura y red | [`docs/architecture.md`](../docs/architecture.md), [`docs/architecture.html`](../docs/architecture.html) |
| RDS vs DynamoDB | [`docs/data-justification.md`](../docs/data-justification.md) |
| Despliegue paso a paso y tabla completa de solución de problemas | [`docs/deployment-guide.md`](../docs/deployment-guide.md) |
| Demostración en vivo | [`docs/demo-script.md`](../docs/demo-script.md) |
| Riesgos aceptados | [`docs/risks-and-exceptions.md`](../docs/risks-and-exceptions.md) |
| Decisiones | [`specs/adr/`](../specs/adr/) |

Los documentos enlazados están en inglés, como el resto del repositorio.

## 1. Qué se despliega

```
Navegador ──HTTPS──► CloudFront ──/ ────────► S3 frontend (OAC, privado)
                                └─/api/*──► ALB :80 ──► ASG de EC2 :8000 (subredes privadas, 2–4 × t3.micro)
                                                         ├─ API (FastAPI, systemd)
                                                         └─ Worker (systemd)
                                                              ├─► RDS MySQL :3306 (usuarios, sesiones)
                                                              ├─► DynamoDB (documents, jobs)   por endpoint de gateway
                                                              ├─► S3 uploads                   por endpoint de gateway
                                                              └─► SNS (correos)                por NAT gateway
Alarmas de CloudWatch ──► SNS ops-alarms      El historial de eventos de CloudTrail registra las llamadas a la API
```

- **Red:** VPC `10.0.0.0/16` en dos zonas de disponibilidad. Las subredes públicas tienen el ALB y el NAT gateway. Las privadas tienen las instancias y la base de datos. Los security groups se encadenan `alb-sg → app-sg → db-sg`; ninguno abre el puerto 22.
- **Cómputo:** un solo Auto Scaling Group ejecuta la API y el worker en cada instancia. Las instancias arrancan con Ubuntu 24.04 porque ahí Tesseract está empaquetado (`ADR-038`).
- **Datos:** RDS MySQL guarda usuarios y sesiones; DynamoDB guarda documentos, jobs y resultados; S3 guarda los archivos originales. La tabla `jobs` es la cola de trabajo (`ADR-010`).
- **IaC:** raíz de Terraform en `infra/terraform/` con 12 módulos. Los cuatro buckets de S3 son un stack de CloudFormation que Terraform crea y destruye (`ADR-035`). Terraform no crea ningún recurso de IAM; las instancias usan el instance profile preexistente del lab.

### Módulos de Terraform

| Módulo | Crea |
|---|---|
| `network` | VPC, seis subredes, Internet gateway, NAT gateway, tablas de rutas, endpoints de gateway para S3 y DynamoDB |
| `security` | Security groups `alb-sg`, `app-sg`, `db-sg` |
| `buckets` | Stack de CloudFormation con los buckets de archivos subidos, artefactos, frontend y logs de auditoría |
| `bucket_policies` | Políticas de bucket que dan acceso al rol de la instancia (`ADR-033`) |
| `alb` | Balanceador, target group, listener |
| `compute` | Launch template (volumen raíz gp2, userData), Auto Scaling Group, política de target tracking |
| `database` | Instancia RDS MySQL, subnet group, contraseña en SSM Parameter Store |
| `dynamodb` | Tablas `documents` y `jobs` con sus índices |
| `frontend` | Distribución de CloudFront, OAC, políticas de caché y de cabeceras de respuesta |
| `messaging` | Tópicos SNS `processing-events` y `ops-alarms`, suscripciones por correo, políticas de los tópicos |
| `monitoring` | Siete alarmas de CloudWatch y un dashboard |
| `audit` | Trail de CloudTrail (desactivado por defecto: el lab niega `CreateTrail`, `INF-AUD-03`) |

### Configuración de las instancias

`infra/terraform/templates/userdata.sh.tftpl` se ejecuta en el primer arranque de cada instancia:

1. instala Python, Tesseract (`spa`, `eng`) y los paquetes del sistema con `apt`;
2. descarga el bundle de CA de RDS, lee la contraseña de la base de datos de SSM Parameter Store y escribe `/etc/docuprocess/app.env`;
3. descarga la versión `releases/<versión>/docuprocess-<versión>.tar.gz` del bucket de artefactos;
4. instala las dependencias fijadas y los tres paquetes de la aplicación en un entorno virtual;
5. ejecuta las migraciones (solo hacia adelante) por TLS, verificando el certificado contra la CA de RDS, bajo un lock de MySQL para que dos instancias nunca migren a la vez;
6. arranca los servicios de systemd `docuprocess-api` y `docuprocess-worker`.

El log del arranque es `/var/log/docuprocess-bootstrap.log`.

## 2. Requisitos previos

- Ubuntu 24.04 (nativo o WSL) con `make`, Git, Python 3.12, [uv](https://docs.astral.sh/uv/), Terraform ≥ 1.6, AWS CLI v2 y, para acceder por terminal, el plugin de Session Manager.
- Tesseract con datos de español e inglés para las pruebas locales:
  ```sh
  sudo apt-get install -y make python3-venv tesseract-ocr tesseract-ocr-spa tesseract-ocr-eng
  ```
- Un lab de AWS Academy iniciado y un correo para recibir las notificaciones.

## 3. Desplegar

### 3.1 Preparar y verificar en local

```sh
make setup        # instala las dependencias fijadas
make lint         # ruff, terraform fmt, guardia de restricciones del sandbox, búsqueda de secretos
make test         # pruebas unitarias y de contrato, sin llamadas a AWS
make tf-validate  # terraform init -backend=false + validate
```

Todos los comandos deben terminar con código 0. Todavía no se crea nada en AWS.

### 3.2 Conectarse al sandbox

1. Copiar el bloque *AWS CLI* del lab en `~/.aws/credentials`, bajo `[default]`. Nunca poner credenciales en el repositorio.
2. Configurar la región y verificar la sesión:
   ```sh
   aws configure set region us-east-1
   bash scripts/aws_sandbox_check.sh
   ```
3. Buscar el nombre del instance profile. Cambia en cada sesión del lab:
   ```sh
   aws iam list-instance-profiles \
     --query "InstanceProfiles[?contains(InstanceProfileName,'SsmRoleInstanceProfile')].InstanceProfileName" \
     --output text
   ```

### 3.3 Configurar

```sh
cp infra/terraform/terraform.tfvars.example infra/terraform/terraform.tfvars
```

Valores en `terraform.tfvars` (el archivo está en `.gitignore`):

| Variable | Valor |
|---|---|
| `instance_profile_name` | el nombre encontrado en 3.2 |
| `alert_email` | el correo que recibe los avisos de jobs y alarmas |
| `release_version` | `"1.0.0"` |
| `asg_health_check_type` | `"ELB"` |

Revisar el plan antes de cualquier escritura:

```sh
make tf-plan
```

Verificar que el plan no tenga recursos de IAM, Lambda, RDS público ni reglas de SSH.

### 3.4 Desplegar con un comando

```sh
make up VERSION=1.0.0
```

`make up` ejecuta estos pasos en orden y se detiene en el primer fallo:

| Paso | Target | Qué hace |
|---|---|---|
| 1 | `prepare-state` | Reconcilia el estado local de Terraform con el lab: aparta el estado de una sesión anterior e importa los recursos que sobreviven a un reset del lab (`ADR-040`) |
| 2 | `package` | Construye `dist/docuprocess-1.0.0.tar.gz` |
| 3 | `bootstrap-artifacts` | Aplica el módulo `buckets` (stack de CloudFormation) |
| 4 | `publish` | Sube la versión al bucket de artefactos |
| 5 | `deploy` | Planea y aplica el stack completo con health checks del ELB |
| 6 | `deploy-frontend` | Sube el portal a S3 e invalida la caché de CloudFront |
| 7 | `scripts/wait_healthy.sh` | Espera a que el target group tenga 2 targets sanos (límite de 20 minutos) e imprime la URL de CloudFront |

Un despliegue completo tarda unos 20 minutos, la mayor parte en crear RDS y en el arranque de las instancias.

### 3.5 Confirmar y probar

1. Abrir los dos correos de confirmación de SNS (`processing-events`, `ops-alarms`) y confirmar ambas suscripciones.
2. Ejecutar la prueba de humo de extremo a extremo:
   ```sh
   SMOKE_BASE_URL=https://$(terraform -chdir=infra/terraform output -raw cloudfront_domain_name) make smoke
   ```
   Registra un usuario sintético, sube una muestra, consulta hasta llegar a un estado terminal y cierra la sesión.
3. En el navegador, subir `samples/receipts/receipt.pdf`. El estado pasa por `PENDING → RUNNING → COMPLETED` y el total es COP 119000.00. Llega un correo con el ID del documento y el estado.
4. Ejecutar `make tf-plan` otra vez: no debe reportar cambios.

## 4. Operar

Atajos usados abajo:

```sh
tf() { terraform -chdir=infra/terraform "$@"; }
ASG=$(tf output -raw asg_name)
TG=$(tf output -raw target_group_arn)
```

### 4.1 Revisar la salud

```sh
aws elbv2 describe-target-health --target-group-arn "$TG" \
  --query "TargetHealthDescriptions[].[Target.Id,TargetHealth.State]" --output table
aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names "$ASG" \
  --query "AutoScalingGroups[0].[MinSize,MaxSize,DesiredCapacity]" --output text
curl -s "https://$(tf output -raw cloudfront_domain_name)/api/v1/health"
```

El endpoint de salud verifica RDS y DynamoDB, así que un target sano significa que toda la ruta de datos funciona.

### 4.2 Abrir una terminal en una instancia

No hay SSH. Se usa Session Manager:

```sh
aws ssm start-session --target <id-de-instancia>
```

O desde la consola: EC2 → instancia → Connect → Session Manager. Comandos útiles en la instancia:

```sh
systemctl status docuprocess-api docuprocess-worker
sudo journalctl -u docuprocess-worker -n 100 --no-pager
sudo tail -n 100 /var/log/docuprocess-bootstrap.log
```

Los logs contienen solo IDs, códigos y tiempos; nunca contenido de documentos, correos ni montos (`SEC-LOG-02`).

### 4.3 Revisar los jobs

```sh
aws dynamodb scan --table-name "$(tf output -raw jobs_table_name)" \
  --projection-expression "job_id,#s,attempts,notification_status" \
  --expression-attribute-names '{"#s":"status"}' --output table
```

Un job pasa por `PENDING → RUNNING → COMPLETED | PARTIAL | FAILED`. El worker tiene un lease de 300 segundos; si una instancia muere, el lease expira y otro worker reintenta el job, hasta el límite de reintentos (`ADR-026`).

### 4.4 Escalado

El Auto Scaling Group mantiene entre 2 y 4 instancias y apunta a un 60 % de CPU promedio. Para verlo reaccionar:

```sh
make load           # 4 clientes durante 10 minutos; LOAD_WORKERS y LOAD_MINUTES lo cambian
aws autoscaling describe-scaling-activities --auto-scaling-group-name "$ASG" --max-items 5 --output table
```

El lab niega el monitoreo detallado, así que la CPU llega cada 5 minutos y el escalado tarda de 8 a 12 minutos de carga sostenida. Observado el 2026-11-11: la CPU promedio llegó al 65 % a los 5 minutos, la alarma se disparó hacia los 7,5 minutos y la tercera instancia quedó en servicio hacia los 8 minutos. Hay que mantener la concurrencia baja: 24 clientes de inicio de sesión simultáneos agotaron la memoria de la `t3.micro` (ver `docs/risks-and-exceptions.md`).

### 4.5 Alarmas y auditoría

```sh
aws cloudwatch describe-alarms --alarm-name-prefix docuprocess \
  --query "MetricAlarms[].[AlarmName,StateValue]" --output table
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=CreateAutoScalingGroup --max-results 3
```

Las alarmas notifican al tópico `ops-alarms`. El lab niega la creación de trails, así que la auditoría usa el historial de eventos de CloudTrail (90 días de eventos de administración).

### 4.6 Publicar una nueva versión

1. Empaquetar y publicar con un número de versión nuevo: `make package VERSION=1.0.1 && make publish VERSION=1.0.1`.
2. Aplicar: `make deploy VERSION=1.0.1`, y poner `release_version` en `terraform.tfvars`.
3. El lab niega el instance refresh, así que se reemplazan las instancias de a una, esperando a que cada nueva esté sana (`ADR-039`):
   ```sh
   aws autoscaling terminate-instance-in-auto-scaling-group \
     --instance-id <id-de-instancia> --no-should-decrement-desired-capacity
   ```

Los datos de RDS, DynamoDB y S3 se conservan al reemplazar instancias.

### 4.7 Después de un reset del lab

Un reset del lab borra casi todos los recursos, pero conserva el parámetro con la contraseña de la base de datos y dos políticas de CloudFront, mientras el estado local sigue listando los recursos borrados. Basta con volver a ejecutar `make up`: su primer paso, `make prepare-state`, reconcilia el estado.

### 4.8 Destruir

```sh
make destroy
```

Muestra el plan de destrucción, vacía todos los buckets (incluidas las versiones) y luego ejecuta `terraform destroy` con su propia confirmación. Después hay que verificar que EC2, RDS, el NAT gateway, CloudFront y los buckets ya no existan.

## 5. Solución de problemas

| Síntoma | Causa | Solución |
|---|---|---|
| Los targets no quedan sanos | Falló el arranque, o RDS/DynamoDB no son alcanzables | Leer `/var/log/docuprocess-bootstrap.log` y `journalctl -u docuprocess-api` por SSM; `curl -i localhost:8000/api/v1/health` |
| Falla la descarga de la versión al arrancar | Versión no publicada o clave equivocada | Publicar la misma versión antes de desplegar; revisar la política del bucket de artefactos |
| `apt` se queda colgado en la instancia | No hay ruta a Internet | Revisar que la tabla de rutas privada apunte al NAT gateway |
| `RunInstances` denegado | Volumen raíz gp3 o tipo de instancia no permitido | El launch template mapea un volumen raíz gp2 (`ADR-034`); usar t2/t3 hasta medium |
| Error de TLS o de conexión con RDS | Security group o descarga de la CA | Verificar que `db-sg` permita el 3306 desde `app-sg`; mantener la verificación del certificado |
| `...AlreadyExists` durante el despliegue | Restos de un reset del lab | `make prepare-state` y desplegar de nuevo (`ADR-040`) |
| No llega el correo | Suscripción sin confirmar | Confirmar la suscripción de SNS; revisar `notification_status` en el job |
| El portal muestra una versión vieja | Caché de CloudFront | `make deploy-frontend` (sube e invalida `/*`) |
| `AccessDenied` desde Terraform | Restricción del sandbox | Comparar con `specs/02-aws-sandbox-constraints.md`; no rodearla con IAM |
| El ALB responde 502 bajo carga | Demasiados inicios de sesión simultáneos para la memoria de la `t3.micro` | Bajar `LOAD_WORKERS`; esperar a que el ASG reemplace la instancia |

La tabla completa está en [`docs/deployment-guide.md`](../docs/deployment-guide.md#troubleshooting).
