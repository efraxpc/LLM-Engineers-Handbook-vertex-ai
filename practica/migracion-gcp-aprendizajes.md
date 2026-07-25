# Migración AWS → GCP: aprendizajes

Estado al 2026-07-25: el pipeline ETL (`digital_data_etl`) corre de punta a punta en Vertex AI Pipelines, verificado en la API de Vertex (`PIPELINE_STATE_SUCCEEDED`).

## Decisiones de la migración

- **MongoDB → Firestore** con compatibilidad MongoDB (endpoint `*.firestore.goog:443`, misma URI/driver de Mongo).
- **ZenML Cloud usa *projects*, ya no *workspaces*** como unidad de organización.
- **ECR → Artifact Registry de GCP** como container registry del stack (`zenml container-registry connect gcp_registry --connector gcp_connector`).
- **SageMaker → Vertex AI** como orquestador (`gcp_vertex` en el stack `gcp-stack`).

## Aprendizajes técnicos

1. **`docker push` sube al registry que indica el prefijo del tag, no "a Docker".** `us-east1-docker.pkg.dev/mdk-gcengine-lab-502313/zenml-llmtwin/llmtwin:latest` va a Artifact Registry de GCP; sin dominio iría a Docker Hub; con `*.dkr.ecr.*.amazonaws.com` iría a ECR. La autenticación de Docker es **por dominio**: `gcloud auth configure-docker us-east1-docker.pkg.dev` registra a gcloud como credential helper para ese registry. Docker Hub solo aparece como origen de la imagen base (`python:3.11-slim-bullseye`) al construir.

2. **`skip_build: True` + `parent_image` traslada la responsabilidad a ti.** ZenML no construye ni sube la imagen: asume que ya existe en el registry. Los YAML pueden apuntar a una imagen que nadie subió (el repo estaba en 0 MB) y no falla hasta que Vertex intenta el pull.

3. **La config del orquestador no se traduce entre orquestadores.** El bloque `orchestrator.sagemaker: synchronous: false` de los YAML se elimina al migrar; no aplica a Vertex.

4. **La imagen debe contener las dependencias del *stack*, no solo las del código.** Cada paso carga el stack de ZenML dentro del contenedor y necesita la integración `gcp` (`google-cloud-pipeline-components`, `google-cloud-run`, `google-cloud-logging`). El venv local los tenía (`zenml integration install gcp`) y enmascaraba que el grupo `gcp` de `pyproject.toml` estaba incompleto → `ImportError` solo en remoto. Fix: agregarlos al grupo y reconstruir la imagen.

5. **El Service Agent de Vertex necesita leer el repo de imágenes.** `service-<project_number>@gcp-sa-aiplatform-cc.iam.gserviceaccount.com` (cuenta de Google, distinta del service account del stack) requiere *Artifact Registry Reader* sobre el repositorio; sin eso el job muere al crearse.

6. **No confiar en el "completed successfully" del cliente de ZenML.** Llegó a imprimirse para un job que quedó `CANCELLED`. El estado real está en la consola de Vertex o la API `pipelineJobs` (con detalle por tarea en `taskDetails`).

7. **Los errores reales de los pasos viven en Cloud Logging.** El log local solo dice qué tarea del DAG falló; el error concreto (el `ImportError`) aparece con `gcloud logging read` sobre el custom job del paso. Flujo de debug: exit code local → API `pipelineJobs` → Cloud Logging.

8. **`:latest` + relanzar rápido = correr con la imagen vieja.** Un job lanzado mientras el push seguía en curso descargó la imagen anterior y falló idéntico. Esperar a que el push termine, o usar tags inmutables por versión.

9. **Cada lanzamiento es un job facturable y sin caché.** `digital_data_etl` tiene caching deshabilitado; los lanzamientos duplicados crawlean todo de nuevo (los documentos se upsertean por URL, así que no corrompen datos, pero se paga el cómputo).

10. **Poetry 2.x eliminó `poetry lock --no-update`**; ahora `poetry lock` a secas conserva los pins existentes.

## Pendiente

- **Qdrant apunta a `localhost:6333`**: el pipeline de feature engineering fallará en Vertex hasta tener un Qdrant accesible desde GCP (Qdrant Cloud o desplegado en el proyecto).
- Commitear `pyproject.toml`, `poetry.lock` y los `configs/digital_data_etl_*.yaml` modificados.
