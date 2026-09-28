# App Fichaje

Aplicación web SaaS de **control horario / fichaje de empleados** para varias empresas (multi-tenant).

Cada empresa tiene su propio **terminal de fichaje** (`/clock/{slug}`), que puede ser un móvil, una tablet o un PC. Los empleados fichan en él con un PIN. Los administradores gestionan empleados, fichajes, informes y auditoría desde el **panel de administración** (`/admin`).

> Estado: **fase 3 — modelo de datos**. Todavía no hay lógica de negocio (ver [Estado actual](#estado-actual)).

---

## Arquitectura

```
Navegador ──► Frontend (React SPA, Vite)
                 │  /api/*  (proxy de Vite en desarrollo)
                 ▼
              Backend (FastAPI)  ──►  PostgreSQL
```

- **Monolito modular**: un solo backend dividido en módulos de dominio (empresas, empleados, fichaje…).
- **Una sola SPA** con dos experiencias: el terminal (`/clock/:companySlug`) y la administración (`/admin`). Cada pantalla se carga bajo demanda (lazy loading).
- **Una única base de datos PostgreSQL** compartida por todas las empresas. Los datos se aíslan con `company_id`, y el backend determina siempre la empresa a partir de la credencial, nunca de lo que envíe el frontend.
- **La lógica de negocio vive en el backend.** La hora oficial de cada fichaje es la del servidor (UTC).

## Tecnologías

| Parte | Tecnologías |
|---|---|
| Frontend | React, TypeScript, Vite, Tailwind CSS, React Router |
| Backend | Python 3.13, FastAPI, Pydantic Settings, SQLAlchemy, Alembic, Pytest |
| Base de datos | PostgreSQL 17 |
| Entorno de desarrollo | Docker + Docker Compose |

Se incorporarán en sus fases: TanStack Query, React Hook Form, Zod, JWT y PWA.

## Estructura de carpetas

```
.
├── docker-compose.yml       # Entorno de desarrollo: db + backend + frontend
├── .env.example             # Plantilla de variables de entorno (sin secretos reales)
├── docs/                    # Documentación técnica (modelo de datos)
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml       # Dependencias y configuración de pytest
│   ├── alembic.ini          # Configuración de migraciones
│   ├── alembic/             # Entorno y migraciones de Alembic
│   ├── app/
│   │   ├── main.py          # Crea la app FastAPI
│   │   ├── core/            # Configuración e infraestructura común
│   │   ├── db/              # Base declarativa, engine, sesiones y registro de modelos
│   │   ├── tenancy/         # Contexto de empresa (TenantContext)
│   │   ├── auth/            # Autenticación de administración y permisos
│   │   ├── api/             # deps.py (dependencias comunes) y v1/ (router y /health)
│   │   └── modules/         # companies, users, employees, terminals, clock, reports, audit (models.py en cada uno)
│   └── tests/               # conftest.py prepara la base de datos de tests
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── vite.config.ts       # Plugins, proxy /api y servidor de desarrollo
    ├── index.html
    └── src/
        ├── main.tsx         # Punto de entrada
        ├── index.css        # Tailwind
        ├── app/             # Router y páginas globales
        ├── features/        # Una carpeta por funcionalidad (terminal, admin, employees…)
        └── shared/          # api, ui, lib, schemas compartidos
```

## Requisitos previos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (incluye Docker Compose), **arrancado**.
- No hace falta tener Python ni Node instalados: todo se ejecuta en contenedores.

## Arrancar el proyecto

```bash
# 1. Solo la primera vez: crear tu archivo de variables de entorno
cp .env.example .env          # en PowerShell: Copy-Item .env.example .env

# 2. Levantar el entorno (la primera vez construye las imágenes)
docker compose up --build
```

Las siguientes veces basta con `docker compose up`. Para dejarlo en segundo plano, usa `docker compose up -d`.

Solo hace falta reconstruir las imágenes (`--build`) cuando cambian las dependencias (`pyproject.toml` o `package.json`). Los cambios de código se recargan solos.

## Detener el proyecto

```bash
docker compose down        # detiene y elimina los contenedores; los datos de PostgreSQL se conservan
docker compose down -v     # además BORRA el volumen de PostgreSQL (todos los datos)
```

## URLs

| Servicio | URL |
|---|---|
| Terminal de fichaje (ejemplo) | http://localhost:5173/clock/detapas |
| Panel de administración | http://localhost:5173/admin |
| Health del backend | http://localhost:8000/api/v1/health |
| Health a través del proxy del frontend | http://localhost:5173/api/v1/health |
| Documentación de la API (Swagger) | http://localhost:8000/docs |
| PostgreSQL | `localhost:5432` (usuario, contraseña y BD definidos en `.env`) |

## Comandos útiles

```bash
docker compose exec backend pytest            # tests del backend (usan la BD fichaje_test)
docker compose exec backend alembic upgrade head  # aplicar las migraciones pendientes
docker compose exec backend alembic current   # revisión aplicada en la BD de desarrollo
docker compose exec backend alembic check     # ¿hay cambios en los modelos sin migración?
docker compose exec frontend npm run typecheck # comprobación de tipos del frontend
docker compose logs -f backend                # ver logs de un servicio
```

## Variables de entorno

`.env.example` separa la **configuración** (entorno, puertos, nombre de la BD) de los **secretos** (contraseña de la BD, `JWT_SECRET`, `PIN_HMAC_SECRET`).

- `.env` nunca se sube al repositorio.
- El código no contiene valores: los lee del entorno ([backend/app/core/config.py](backend/app/core/config.py)).

## Base de datos

- **Conexión**: SQLAlchemy 2.x con psycopg 3. La URL sale de `DATABASE_URL` ([backend/app/db/session.py](backend/app/db/session.py)).
- **Sesión por petición**: los endpoints reciben una sesión con la dependencia `DbSession` ([backend/app/api/deps.py](backend/app/api/deps.py)). Si el endpoint termina bien se hace *commit*; si lanza una excepción, *rollback*. La sesión se cierra siempre, y todo ocurre **antes** de enviar la respuesta.
- **Modelo de datos**: 8 tablas (empresas, usuarios, empleados, terminales, jornadas, pausas, eventos de fichaje y auditoría). Ver **[docs/modelo-de-datos.md](docs/modelo-de-datos.md)**.
- **Modelos**: heredan de `Base` ([backend/app/db/base.py](backend/app/db/base.py)) y se registran en [backend/app/db/models.py](backend/app/db/models.py) para que Alembic los detecte.
- **Identificadores**: UUID nativo de PostgreSQL (`Mapped[uuid.UUID]`).
- **Fechas y horas**: siempre `TIMESTAMP WITH TIME ZONE` (`Mapped[datetime]`). La aplicación trabaja con instantes en **UTC**. La zona horaria de cada empresa se guarda como nombre **IANA** (p. ej. `Europe/Madrid`) y solo se usa para mostrar y agrupar por día o semana.
- **Constraints e índices**: con nombres deterministas (convención de nombres en `Base.metadata`).
- **Health**: `GET /api/v1/health` responde `200 {"status":"ok","database":"ok"}`, o `503 {"status":"degraded","database":"unavailable"}` si PostgreSQL no está disponible. El detalle del error solo aparece en los logs.

### Base de datos de tests

Los tests **nunca** usan la base de datos de desarrollo. Usan `fichaje_test` (el nombre de `DATABASE_URL` + `_test`) en el mismo servidor PostgreSQL, y la crean automáticamente si no existe. Se puede usar otra con `TEST_DATABASE_URL`, pero su nombre debe terminar en `_test`. Al empezar, su esquema se reconstruye con las migraciones reales (`alembic upgrade head`). Cada test trabaja dentro de una transacción que se deshace al terminar ([backend/tests/conftest.py](backend/tests/conftest.py)).

## Estado actual

**Implementado (fase 1):**

- Monorepo con backend y frontend.
- Docker Compose con PostgreSQL (volumen persistente), backend y frontend con recarga automática.
- Backend FastAPI con `GET /api/v1/health`.
- Alembic configurado, sin migraciones.
- Frontend con React Router, Tailwind y dos pantallas provisionales: `/clock/:companySlug` y `/admin`.

**Implementado (fase 2):**

- Conexión a PostgreSQL con SQLAlchemy 2.x: engine, sesiones y sesión por petición con commit/rollback.
- Base declarativa con convención de nombres, UUID y timestamps con zona horaria.
- Alembic conectado al metadata de los modelos (todavía sin modelos ni migraciones).
- Health que comprueba también PostgreSQL.
- Base de datos de tests separada y tests de conexión, sesión y health.

**Implementado (fase 3):**

- Modelo de datos: `companies`, `users`, `employees`, `terminals`, `work_sessions`, `work_breaks`, `clock_events` y `audit_logs`.
- Aislamiento multiempresa en la base de datos con claves foráneas compuestas `(company_id, x_id)`.
- Constraints, índices y la migración inicial, reversible.
- Inmutabilidad de eventos y auditoría a nivel de ORM.
- Tests del modelo de datos.

**Pendiente (fases siguientes):** autenticación, gestión de empresas y empleados, PIN, terminales, fichaje, horas, auditoría, panel de administración, PWA, hardening y producción.
