# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

The LLM Engineer's Handbook companion repo: an "LLM Twin" system built as ZenML MLOps pipelines — data crawling (ETL) → feature engineering into a vector DB → instruct/preference dataset generation → fine-tuning & evaluation (AWS SageMaker) → RAG inference (FastAPI). Python 3.11, Poetry, with tasks orchestrated via Poe the Poet.

This fork is being migrated from the book's AWS stack to GCP: Vertex AI Pipelines as orchestrator (`gcp-stack`), Artifact Registry for the pipeline image (`us-east1-docker.pkg.dev/mdk-gcengine-lab-502313/zenml-llmtwin/llmtwin:latest`, referenced via `parent_image` + `skip_build: True` in `configs/digital_data_etl_*.yaml`), and Firestore's MongoDB-compatible endpoint instead of local MongoDB. After changing dependencies, rebuild and push that image or remote runs will use the stale one. Migration learnings and pending work: `practica/migracion-gcp-aprendizajes.md`.

## Commands

All commands are Poe tasks defined in `pyproject.toml`. Run them as `poetry poe <task>`.

```bash
poetry install                        # base deps (add --with aws for SageMaker deps, --with gcp for Vertex AI deps)

# QA
poetry poe lint-check                 # ruff check .
poetry poe lint-fix
poetry poe format-check               # ruff format --check .
poetry poe format-fix
poetry poe test                       # pytest tests/ with ENV_FILE=.env.testing
```

To run a single test, replicate what `poe test` does (the env file matters — settings are loaded at import time):

```bash
ENV_FILE=.env.testing poetry run pytest tests/unit/unit_example_test.py::test_name
```

### Local infrastructure

Pipelines need MongoDB + Qdrant (docker compose) and a local ZenML server:

```bash
poetry poe local-infrastructure-up    # docker compose up + zenml login --local
poetry poe local-infrastructure-down
```

ZenML dashboard: http://localhost:8237, Qdrant: http://localhost:6333, MongoDB on 27017.

### Pipelines

```bash
poetry poe run-digital-data-etl                        # crawl configured links into MongoDB
poetry poe run-feature-engineering-pipeline            # clean → chunk → embed → load Qdrant
poetry poe run-generate-instruct-datasets-pipeline
poetry poe run-generate-preference-datasets-pipeline
poetry poe run-end-to-end-data-pipeline                # all of the above in one go
poetry poe run-training-pipeline                       # SageMaker fine-tuning
poetry poe run-evaluation-pipeline

# Inference
poetry poe call-rag-retrieval-module                   # tools/rag.py demo
poetry poe run-inference-ml-service                    # uvicorn tools.ml_service:app on :8000
poetry poe call-inference-ml-service                   # curl the /rag endpoint
```

AWS-related tasks: `set-aws-stack`, `deploy-inference-endpoint`, `delete-inference-endpoint`, `create-sagemaker-role`, `create-sagemaker-execution-role`, `export-settings-to-zenml`.

## Architecture

Execution flow: `tools/run.py` (Click CLI, one flag per pipeline) → `pipelines/` (ZenML pipeline definitions) → `steps/` (ZenML steps, grouped by pipeline stage) → `llm_engineering/` (the core package). Pipelines are parameterized by the YAML files in `configs/` (each `--run-*` flag maps to a config file).

`llm_engineering/` follows DDD layering; imports flow `infrastructure` → `model` → `application` → `domain` (lower layers must not import higher ones):

- `domain/` — Pydantic entities. Two ODM-style generic base classes do the persistence heavy lifting: `domain/base/nosql.py` (`NoSQLBaseDocument`, MongoDB) and `domain/base/vector.py` (`VectorBaseDocument`, Qdrant). Documents map to collections via class config; subclass these rather than talking to the DB clients directly.
- `application/` — crawlers (dispatched by URL via `crawlers/dispatcher.py`), preprocessing, RAG (query expansion, self-query, retrieval, reranking), dataset generation.
- `model/` — SageMaker fine-tuning, evaluation, and inference code.
- `infrastructure/` — MongoDB/Qdrant connections, AWS deploy/roles, the FastAPI inference app (`inference_pipeline_api.py`), Opik utils.

A recurring pattern is dispatcher + handler factory keyed on `DataCategory` (posts / articles / repositories): `application/preprocessing/dispatchers.py` routes each document to the right cleaning/chunking/embedding handler. To support a new data category, add a domain entity plus a handler for each preprocessing stage and register it in the factories.

### Settings

`llm_engineering/settings.py` defines a Pydantic `Settings` loaded at import time: it first tries the ZenML secret store (secret named `settings`, pushed via `poetry poe export-settings-to-zenml`), then falls back to `.env`. Anything importing `llm_engineering` therefore triggers settings loading — this is why tests set `ENV_FILE=.env.testing`.

## Conventions

- Ruff is the linter and formatter (config in `ruff.toml`): line length 120, isort, Google-style docstrings.
- CI (`.github/workflows`) runs the QA tasks and tests; `lint-check-docker` (hadolint) and `gitleaks-check` exist as Poe tasks too.
