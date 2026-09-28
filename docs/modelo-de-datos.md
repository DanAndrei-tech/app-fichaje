# Modelo de datos

Modelo relacional de App Fichaje (diseño aprobado en la fase 03A, implementado en la 03B).

- Modelos: `backend/app/modules/*/models.py`
- Migración: `backend/alembic/versions/*_initial_data_model.py`
- Tests: `backend/tests/models/`

## Resumen

| Tabla | Qué guarda |
|---|---|
| `companies` | Empresas (tenants). |
| `users` | Cuentas de administración (ADMIN, MANAGER; PLATFORM_ADMIN preparado). |
| `employees` | Personas que fichan con PIN. |
| `terminals` | Dispositivos autorizados para fichar. |
| `work_sessions` | Jornadas: la interpretación de los fichajes. Se corrigen con auditoría. |
| `work_breaks` | Pausas dentro de una jornada. |
| `clock_events` | Eventos originales del terminal. **Inmutables.** |
| `audit_logs` | Quién cambió qué, cuándo y por qué. **Inmutables.** |

El estado del empleado **no se guarda en ninguna columna**, se deduce:

- **OFF:** no tiene ninguna jornada `OPEN`.
- **WORKING:** tiene una jornada `OPEN` sin pausa abierta.
- **ON_BREAK:** tiene una jornada `OPEN` con una pausa abierta.

## Relaciones

```
companies ─1:N─ users              (0..1 empresa por usuario; PLATFORM_ADMIN sin empresa)
companies ─1:N─ employees
companies ─1:N─ terminals
companies ─1:N─ work_sessions, work_breaks, clock_events   (company_id directo)
companies ─1:N─ audit_logs         (company_id NULL = acción de plataforma)

employees     ─1:N─ work_sessions  (máx. 1 OPEN)
employees     ─1:N─ clock_events
work_sessions ─1:N─ work_breaks    (máx. 1 pausa abierta)
work_sessions ─1:N─ clock_events   (cada evento apunta a la jornada que abrió o modificó)
terminals     ─1:N─ clock_events
users         ─1:N─ audit_logs     (actor, solo si actor_type = USER)
```

## Convenciones

- **Claves primarias:** UUIDv4 generado en la aplicación.
- **Fechas y horas:** `TIMESTAMPTZ`, siempre instantes en UTC.
- **Zona horaria de la empresa:** nombre IANA (`Europe/Madrid`). Se usa solo para calcular `work_date`, mostrar horas y agrupar informes. La zona del dispositivo se ignora.
- **`work_date`:** día laboral, que es la fecha local de la empresa en el momento del CLOCK_IN. Un turno de 22:00 a 06:00 pertenece al día de entrada. Lo calculará el servicio de fichaje.
- **Duración de una jornada:** `ended_at − started_at − Σ pausas`, restando instantes UTC. Así los cambios de hora salen correctos sin tratamiento especial.
- **Enumerados:** `VARCHAR` con `CHECK`, no ENUM nativo, porque son más fáciles de migrar. En Python son `StrEnum`.
- **Nombres de constraints e índices:** deterministas, `pk_`, `fk_`, `uq_`, `ck_`, `ix_` + tabla + columnas.
- **`created_at` y `updated_at`:** los pone PostgreSQL (`now()`).

## Multiempresa

1. **Todas las tablas de negocio tienen `company_id`**, aunque se pudiera deducir de otra tabla. Así cada consulta filtra por empresa directamente y una futura RLS es trivial.
2. **Claves foráneas compuestas.** Las tablas referenciadas exponen `UNIQUE (company_id, id)` y las hijas apuntan a ese par:

   ```
   work_sessions (company_id, employee_id)     → employees     (company_id, id)
   work_breaks   (company_id, work_session_id) → work_sessions (company_id, id)
   clock_events  (company_id, employee_id)     → employees     (company_id, id)
   clock_events  (company_id, terminal_id)     → terminals     (company_id, id)
   clock_events  (company_id, employee_id, work_session_id)
                                               → work_sessions (company_id, employee_id, id)
   ```

   PostgreSQL rechaza cualquier fila que mezcle empresas, por ejemplo una jornada de la empresa B para un empleado de la empresa A, venga del código que venga.

   La FK triple de `clock_events` garantiza además que el evento y su jornada son **del mismo empleado**. No se puede registrar un evento del empleado A sobre la jornada del empleado B, aunque ambos sean de la misma empresa.
3. **`company_id` es inmutable:**
   - La aplicación lo impide en el ORM (`immutable_columns`).
   - `ON UPDATE RESTRICT` lo impide en PostgreSQL mientras haya filas hijas.
4. **El backend nunca acepta `company_id` del cliente.** Lo obtiene de la credencial (usuario o terminal) a través de `TenantContext`, que llegará en fases posteriores.

## PIN de empleado

- El PIN tiene 6 dígitos y lo genera el sistema. **Nunca se guarda en claro.**
- `pin_lookup` = `HMAC-SHA256(clave[pin_key_version], f"{company_id}:{pin}")`: 32 bytes en `BYTEA`, con `CHECK octet_length = 32`.
  - La clave HMAC está fuera de la base de datos.
  - `UNIQUE (company_id, pin_lookup)`: un PIN no se repite dentro de una empresa, pero sí puede existir en otra.
- `pin_key_version` indica con qué versión de la clave se calculó el lookup, para poder rotar claves.
- `pin_generated_at` indica cuándo se emitió el PIN actual.
- No hay `pin_hash`. Se decidió en la fase 03A: el HMAC con secreto ya protege y es la forma de verificar.
- **Regenerar el PIN** (cuando el empleado lo olvida) consiste en:
  1. Sustituir `pin_lookup`, `pin_key_version` y `pin_generated_at`.
  2. Con eso, el PIN anterior deja de funcionar.
  3. Registrar `PIN_REGENERATED` en `audit_logs`, **sin valores**.
  - El PIN antiguo nunca se recupera. No hay tabla específica para esto.
- **Pendiente para fases posteriores:** generar el PIN, el login por PIN, el rate limiting y el flujo de regeneración.

## Terminales

- El token del terminal **no se guarda**. Solo se guarda su SHA-256 (`token_hash`, 32 bytes, único).
- Estados:
  - **Activo:** `active = true` y `revoked_at` NULL.
  - **Desactivado:** `active = false`. Es reversible.
  - **Revocado:** `revoked_at` con valor. Es definitivo, y un CHECK obliga a que además `active = false`.
- `name` es único dentro de la empresa.

## Jornadas y pausas

| Estado | Significado | `ended_at` |
|---|---|---|
| `OPEN` | En curso. Como máximo una por empleado (índice único parcial). | Obligatoriamente NULL |
| `CLOSED` | Terminada y válida. | Obligatorio |
| `NEEDS_REVIEW` | Anómala: salida olvidada o duración mayor que `max_shift_hours`. No bloquea una nueva entrada. | NULL o con valor |
| `VOIDED` | Anulada por un administrador. Sustituye al borrado. | NULL o con valor |

**Constraints de jornadas y pausas:**

- `ended_at > started_at`, en jornadas y en pausas.
- Como máximo una pausa abierta por jornada.

**Validaciones que hará el servicio de fichaje** (no caben en un CHECK):

- Que cada pausa quede dentro de su jornada.
- Que las pausas no se solapen entre sí.
- Que las jornadas de un empleado no se solapen.

## Eventos de fichaje (`clock_events`)

- **`occurred_at`:** hora oficial del evento. La pone el servidor, no el dispositivo.
- **`client_reported_at`:** hora que informa el dispositivo. Solo informativa.
- **No hay `created_at`:** coincidiría con `occurred_at`.
- **Idempotencia:** `UNIQUE (terminal_id, idempotency_key, event_type)`. `event_type` forma parte de la clave porque "Finalizar pausa y salir" genera BREAK_END + CLOCK_OUT con una sola petición.
- **Las correcciones administrativas no crean eventos.** Modifican `work_sessions` y `work_breaks` y quedan registradas en `audit_logs`.

## Auditoría (`audit_logs`)

- **Actor:**
  - `actor_type = USER` exige `actor_user_id`.
  - `actor_type = SYSTEM` (procesos automáticos) exige que sea NULL.
  - Lo garantiza un CHECK.
- **Entidad:** `entity_type` + `entity_id`, sin FK porque la entidad puede estar en tablas distintas.
- **`action`:** texto con formato `MAYÚSCULAS_CON_GUIONES`. Las acciones previstas están en `AuditAction`. No hay un CHECK con la lista cerrada, para poder añadir acciones sin migración.
- **`old_value` / `new_value`:** JSONB, **solo con campos permitidos**. Nunca incluyen PIN, `pin_lookup`, contraseñas o su hash, tokens de terminal o su hash, JWT ni refresh tokens.

## Política de borrado

No hay `ON DELETE CASCADE` ni `SET NULL`: **todas las claves foráneas son `ON DELETE RESTRICT` y `ON UPDATE RESTRICT`**. El registro de jornada debe conservarse (4 años en España).

| Tabla | Borrado físico | En su lugar |
|---|---|---|
| companies | No: RESTRICT mientras tenga datos | `active = false` |
| users | No: está referenciado por la auditoría | `active = false` |
| employees | No | `active = false`; anonimizar al vencer el plazo legal |
| terminals | No | `active = false` o `revoked_at` |
| work_sessions | No | `status = VOIDED` |
| work_breaks | Solo como corrección auditada | — |
| clock_events | **Nunca**, ni UPDATE | Inmutable |
| audit_logs | **Nunca**, ni UPDATE | Inmutable |

**Cómo se protege la inmutabilidad hoy:**

- **A nivel de aplicación**, en `app/db/immutability.py`: se rechazan UPDATE y DELETE de objetos y los `update()` o `delete()` masivos del ORM sobre `clock_events` y `audit_logs`, así como los cambios de `companies.slug` y de cualquier `company_id`.
- **A nivel de PostgreSQL** (triggers o permisos) queda para la fase de hardening. Hasta entonces, el SQL escrito a mano puede saltarse esta protección.

## Índices

| Índice | Para qué sirve |
|---|---|
| `uq_companies_slug` | Resolver `/clock/{slug}` |
| `uq_users_email` | Login |
| `uq_employees_company_id_id`, `uq_terminals_company_id_id`, `uq_work_sessions_company_id_id` | Destino de las FK compuestas; también para listar por empresa |
| `uq_work_sessions_company_id_employee_id_id` | Destino de la FK triple de `clock_events` (evento y jornada del mismo empleado) |
| `uq_employees_company_id_pin_lookup` | Unicidad del PIN y búsqueda por PIN |
| `uq_employees_company_id_dni` (parcial, `dni IS NOT NULL`) | DNI único por empresa |
| `uq_terminals_company_id_name`, `uq_terminals_token_hash` | Nombres claros y autenticación del terminal |
| `uq_clock_events_terminal_id_idempotency_key_event_type` | Idempotencia |
| `ix_clock_events_company_id_employee_id_occurred_at` | Historial de un empleado |
| `ix_clock_events_company_id_terminal_id_occurred_at` | Actividad de un terminal |
| `uq_work_sessions_employee_id_open` (parcial, `OPEN`) | Una jornada abierta por empleado y estado actual |
| `ix_work_sessions_company_id_employee_id_work_date` | Horas e historial de un empleado |
| `ix_work_sessions_company_id_work_date` | Informes de empresa por día o semana |
| `ix_work_sessions_company_id_employee_id_needs_review` (parcial) | Bandeja de revisión, por empresa o por empleado |
| `uq_work_breaks_work_session_id_open` (parcial, `ended_at IS NULL`) | Una pausa abierta por jornada |
| `ix_work_breaks_work_session_id_started_at` | Pausas de una jornada, ordenadas |
| `ix_audit_logs_company_id_created_at` | Listado de auditoría de una empresa |
| `ix_audit_logs_entity_type_entity_id_created_at` | Historial de una entidad |

## Pendiente para fases posteriores

- **Tablas nuevas:**
  - `refresh_tokens`.
  - Intentos de PIN, para el rate limiting.
  - Sesión corta de empleado, si se implementa con estado.
- **Hardening:**
  - Triggers de inmutabilidad en PostgreSQL.
  - Restricciones de exclusión (`btree_gist`) contra solapamientos.
  - RLS.
