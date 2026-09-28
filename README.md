# App Fichaje

Aplicación web SaaS de **control horario / fichaje de empleados** para varias empresas (multi-tenant).

Cada empresa tiene su propio **terminal de fichaje** (`/clock/{slug}`), que puede ser un móvil, una tablet o un PC. Los empleados fichan en él con un PIN. Los administradores gestionan empleados, fichajes, informes y auditoría desde el **panel de administración** (`/admin`).

> Estado: **fase 1 — estructura inicial**. Todavía no hay lógica de negocio (ver [Estado actual](#estado-actual)).

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
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml       # Dependencias y configuración de pytest
│   ├── alembic.ini          # Configuración de migraciones
│   ├── alembic/             # Entorno de Alembic (aún sin migraciones)
│   ├── app/
│   │   ├── main.py          # Crea la app FastAPI
│   │   ├── core/            # Configuración e infraestructura común
│   │   ├── tenancy/         # Contexto de empresa (TenantContext)
│   │   ├── auth/            # Autenticación de administración y permisos
│   │   ├── api/v1/          # Router principal y /health
│   │   └── modules/         # companies, users, employees, terminals, clock, reports, audit
│   └── tests/
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
docker compose exec backend pytest            # tests del backend
docker compose exec frontend npm run typecheck # comprobación de tipos del frontend
docker compose logs -f backend                # ver logs de un servicio
```

## Variables de entorno

`.env.example` separa la **configuración** (entorno, puertos, nombre de la BD) de los **secretos** (contraseña de la BD, `JWT_SECRET`, `PIN_HMAC_SECRET`).

- `.env` nunca se sube al repositorio.
- El código no contiene valores: los lee del entorno ([backend/app/core/config.py](backend/app/core/config.py)).

## Estado actual

**Implementado (fase 1):**

- Monorepo con backend y frontend.
- Docker Compose con PostgreSQL (volumen persistente), backend y frontend con recarga automática.
- Backend FastAPI con `GET /api/v1/health` y un test.
- Alembic configurado, sin migraciones.
- Frontend con React Router, Tailwind y dos pantallas provisionales: `/clock/:companySlug` y `/admin`.

**Pendiente (fases siguientes):** conexión a base de datos, modelos, empresas, autenticación, empleados, PIN, terminales, fichaje, horas, auditoría, panel de administración, PWA, hardening y producción.
