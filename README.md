# CPM API — Symbio & Celonis Integration

Herramientas de extracción y sincronización de datos entre **Symbio Business Manager** (CPM), **Celonis** y **AWS S3**.

---

## 📁 Estructura del proyecto

```
cpm_api/
├── .env                        # 🔒 Credenciales (NO se sube a GitHub)
├── .env.example                # Template de credenciales para nuevos devs
├── .gitignore                  # Protege .env y otros archivos generados
├── README.md                   # Este archivo
│
├── APIUsers.ipynb              # Notebook: extracción de usuarios → Celonis
├── processes_backup.ipynb      # Notebook: backup de procesos → AWS S3
│
├── symbio_process_folders.py   # Servicio: obtener carpetas de procesos
└── src/
    ├── components/
    │   └── ProcessFolderDropdown.tsx
    ├── hooks/
    │   └── useProcessFolders.ts
    └── services/
        ├── index.ts
        └── symbioProcessFolders.ts
```

---

## ⚙️ Configuración inicial

### 1. Clonar el repositorio

```bash
git clone <repo-url>
cd cpm_api
```

### 2. Crear el archivo `.env`

Copiar el template y completar con las credenciales reales:

```bash
cp .env.example .env
```

Editar `.env` con los valores correspondientes:

| Variable | Descripción |
|---|---|
| `SYMBIO_BASE_URL` | URL base de Symbio (ej: `https://envalior.symbioweb.com`) |
| `SYMBIO_STORAGE_COLLECTION` | Nombre del storage collection en Symbio |
| `SYMBIO_TENANT` | Nombre del tenant en Symbio |
| `SYMBIO_AUTH_TOKEN` | Token de autenticación generado en Symbio |
| `CELONIS_TEAM_URL` | URL del equipo en Celonis Cloud |
| `CELONIS_API_TOKEN` | API Token de tipo APP_KEY de Celonis |
| `CELONIS_DATA_POOL_ID` | UUID del Data Pool destino en Celonis |
| `AWS_ACCESS_KEY_ID` | Access Key ID de IAM para S3 |
| `AWS_SECRET_ACCESS_KEY` | Secret Access Key de IAM para S3 |
| `AWS_REGION` | Región del bucket S3 (ej: `eu-west-1`) |
| `AWS_S3_BUCKET` | Nombre del bucket S3 para backups |

### 3. Instalar dependencias

```bash
pip install python-dotenv pycelonis requests pandas boto3
```

---

## 📓 Notebooks

### `APIUsers.ipynb` — Extracción de usuarios CPM → Celonis

**Objetivo:** Extraer los usuarios (autores, owners y co-autores) de todos los procesos de Symbio y subirlos como tabla a Celonis.

#### Flujo de ejecución

```
Symbio API (v1)          Celonis (PyCelonis)
┌──────────────┐         ┌──────────────────┐
│ GET /elements│──JSON──▶│ Extraer autores, │
│ (procesos)   │         │ owners, co-autores│
└──────────────┘         └────────┬─────────┘
                                  │
                         ┌────────▼─────────┐
                         │ DataFrame con:   │
                         │ id, name,        │
                         │ last name, email │
                         └────────┬─────────┘
                                  │
                         ┌────────▼─────────┐
                         │ data_pool        │
                         │ .create_table()  │
                         │ → "CPMUsers"     │
                         └──────────────────┘
```

#### Celdas paso a paso

| # | Descripción |
|---|---|
| 1 | Importar librerías y cargar `.env` con `load_dotenv()` |
| 2 | Conectar a Symbio API REST v1 y obtener todos los procesos |
| 3 | Recorrer `elements` → extraer `author`, `owner` y `secondaryAuthors` con sus `expandUri` |
| 4 | Consultar cada `expandUri` → obtener `firstName`, `lastName`, `profileEmail` |
| 5 | Crear `pd.DataFrame(final_user)` |
| 6 | Conectar a Celonis con `get_celonis()` y obtener el Data Pool |
| 7 | Subir DataFrame como tabla `"CPMUsers"` con `create_table()` |
| 8–9 | (Opcional) Obtener carpetas de procesos con `get_process_folder_options()` |

---

### `processes_backup.ipynb` — Backup de procesos BPMN → AWS S3

**Objetivo:** Exportar todos los procesos en estado `inProcess` como archivos `.bpmn` y subirlos a un bucket S3.

#### Flujo de ejecución

```
Symbio API (v1)          Local FS             AWS S3
┌──────────────┐    ┌────────────────┐   ┌────────────────┐
│ GET /elements│──▶ │ Filtrar state  │   │                │
│ (procesos)   │    │ == 'inProcess' │   │                │
└──────────────┘    └───────┬────────┘   │                │
                            │            │                │
                    ┌───────▼────────┐   │                │
                    │ export_bpmn()  │   │                │
                    │ GET /bpmn/{id} │   │                │
                    │ → .bpmn files  │   │                │
                    └───────┬────────┘   │                │
                            │            │                │
                    ┌───────▼────────┐   │                │
                    │ Saved processes/│──▶│ upload_file() │
                    │ *.bpmn         │   │ s3://bucket/   │
                    └────────────────┘   └────────────────┘
```

#### Celdas paso a paso

| # | Descripción |
|---|---|
| 1 | Importar librerías y cargar `.env` con `load_dotenv()` |
| 2 | Conectar a Symbio API REST v1 y obtener todos los procesos |
| 3 | Ver el total de procesos (`views['count']`) |
| 4 | Definir `export_bpmn()` — descarga BPMN XML de un proceso por `versionId` |
| 5 | (Opcional) Borrar archivos `.bpmn` locales de ejecuciones anteriores |
| 6 | Loop: para cada proceso con `state == 'inProcess'` y `type == 'subProcess'`, exportar BPMN |
| 7 | Conectar a AWS S3 con credenciales de `.env` |
| 8 | Borrar todos los objetos existentes en el bucket (para conservar solo la última versión) |
| 9 | Subir todos los `.bpmn` locales al bucket S3 |
| 10 | (Verificación) Listar objetos del bucket |

---

### `symbio_process_folders.py` — Servicio de carpetas de procesos

**Objetivo:** Obtener la estructura jerárquica de carpetas de procesos desde la API v2 de Symbio.

- Usa la API v2 (`/v2/data/elements`) que soporta paginación y filtros
- Modo `recursive=True`: recorre el árbol completo expandiendo cada nodo con `/v2/data/elements/{id}`
- Usa `ThreadPoolExecutor` para paralelizar las llamadas HTTP
- Retorna `list[dict]` con `{"id": str, "name": str}` listo para dropdowns

---

## 🔐 Seguridad

- **Nunca** hacer `git add .env` — el archivo está protegido por `.gitignore`
- Los tokens se cargan en runtime con `python-dotenv` → `load_dotenv()`
- Los outputs de los notebooks fueron limpiados para evitar filtrar datos sensibles en los logs
- Si necesitas rotar credenciales, solo edita el `.env` local

---

## 🚀 Ejecución

Abrir cualquier notebook en Jupyter y ejecutar todas las celdas:

```bash
jupyter notebook APIUsers.ipynb
# o
jupyter notebook processes_backup.ipynb
```

Las credenciales se cargan automáticamente desde `.env` al ejecutar la primera celda.
