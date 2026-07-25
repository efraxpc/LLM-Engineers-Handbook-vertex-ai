<div align="center">
  <h1>👷 LLM Twin — pipelines MLOps na GCP com ZenML e Vertex AI</h1>
  <p>Sistema LLM de ponta a ponta (coleta de dados → feature engineering → geração de datasets → fine-tuning → RAG e inferência) orquestrado com <a href="https://zenml.io">ZenML</a> e implantado no Google Cloud.</p>
</div>

## 🎯 O que é este repositório

Um **LLM Twin**: um sistema que coleta conteúdo publicado por uma pessoa (artigos, posts, repositórios), o transforma em features e datasets, faz fine-tuning de um LLM com esse material e o serve por meio de um sistema RAG — tudo como pipelines MLOps reproduzíveis.

A infraestrutura roda no **Google Cloud**:

| Peça | Serviço GCP |
|---|---|
| Orquestrador de pipelines | **Vertex AI Pipelines** |
| Registro de imagens Docker | **Artifact Registry** |
| Armazenamento de artefatos | **Cloud Storage (GCS)** |
| Data warehouse (documentos) | **Firestore com compatibilidade MongoDB** |
| Servidor ZenML | **ZenML Pro** (SaaS) — ZenML 0.96.2 |

**Status:** o pipeline ETL (`digital_data_etl`) roda de ponta a ponta no Vertex AI, verificado (`PIPELINE_STATE_SUCCEEDED`). Os pipelines de feature engineering, datasets e treinamento ainda rodam no fluxo local.

Um ponto central do projeto: o código Python é agnóstico à nuvem. O ZenML abstrai a infraestrutura (troca-se o *stack*, não o pipeline) e o Firestore fala o protocolo do MongoDB (troca-se a URI de conexão, não a camada ODM baseada em `pymongo`).

## 🗂️ Estrutura do projeto

```bash
.
├── configs/             # YAMLs de configuração por pipeline (imagem Docker, parâmetros)
├── llm_engineering/     # Pacote principal (DDD: domain / application / model / infrastructure)
├── pipelines/           # Definições dos pipelines ZenML
├── steps/               # Passos reutilizáveis dos pipelines
├── tools/               # run.py (CLI dos pipelines), ml_service.py (API REST), rag.py
├── practica/            # Anotações da migração para GCP
└── Dockerfile           # Imagem que executa os passos no Vertex (inclui Chrome para o crawler)
```

## 🔧 Requisitos

- Python 3.11 e [Poetry](https://python-poetry.org) (< 2.0)
- Docker
- [gcloud CLI](https://cloud.google.com/sdk/docs/install) autenticado no seu projeto GCP
- Conta no [ZenML Pro](https://cloud.zenml.io) (teste gratuito)
- Chaves de API: OpenAI (datasets/RAG) e Hugging Face (modelos)

## 💻 Instalação

```bash
poetry install --with gcp
```

Copie `.env.example` para `.env` e preencha suas chaves. As variáveis principais para a GCP:

```bash
DATABASE_HOST=mongodb://<usuario>:<senha>@<UID>.<regiao>.firestore.goog:443/twin?loadBalanced=true&authMechanism=SCRAM-SHA-256&tls=true&retryWrites=false
DATABASE_NAME=twin
OPENAI_API_KEY=...
HUGGINGFACE_ACCESS_TOKEN=...
```

## ☁️ Configuração da GCP (uma única vez)

Resumo do caminho completo; os detalhes e os tropeços estão em [`practica/migracion-gcp-aprendizajes.md`](practica/migracion-gcp-aprendizajes.md).

**1. APIs e recursos base:**

```bash
gcloud services enable aiplatform.googleapis.com storage.googleapis.com artifactregistry.googleapis.com firestore.googleapis.com
gcloud storage buckets create gs://<SEU_BUCKET> --location=<REGIAO>
gcloud artifacts repositories create zenml-llmtwin --repository-format=docker --location=<REGIAO>
```

**2. Service account** com os papéis `Vertex AI User`, `Storage Admin`, `Artifact Registry Writer` e `Service Account User`, e sua chave JSON (`zenml-sa.json`, já ignorada pelo git — **nunca fazer commit dela**).

**3. Firestore com compatibilidade MongoDB:**

```bash
gcloud firestore databases create --database=twin --location=<REGIAO> --edition=enterprise
gcloud firestore user-creds create <usuario> --database=twin   # apenas minúsculas, números e hífens
```

**4. Stack do ZenML** (com sessão iniciada no seu workspace do ZenML Pro):

```bash
zenml service-connector register gcp_connector --type gcp --auth-method=service-account \
    --project_id=<PROJETO> --service_account_json=@zenml-sa.json   # sem --resource-type: multiuso

zenml artifact-store register gcp_artifact_store --flavor gcp --path=gs://<SEU_BUCKET>
zenml container-registry register gcp_registry --flavor=gcp --uri=<REGIAO>-docker.pkg.dev/<PROJETO>/zenml-llmtwin
zenml orchestrator register gcp_vertex --flavor=vertex --project=<PROJETO> --location=<REGIAO>

# conectar cada componente ao connector e, por fim:
zenml stack register gcp-stack -o gcp_vertex -a gcp_artifact_store -c gcp_registry --set
```

**5. Segredos e imagem Docker:**

```bash
poetry poe export-settings-to-zenml        # os contêineres leem a config do secret store do ZenML

poetry poe build-docker-image
gcloud auth configure-docker <REGIAO>-docker.pkg.dev
docker tag llmtwin <REGIAO>-docker.pkg.dev/<PROJETO>/zenml-llmtwin/llmtwin:latest
docker push <REGIAO>-docker.pkg.dev/<PROJETO>/zenml-llmtwin/llmtwin:latest
```

Os YAMLs em `configs/digital_data_etl_*.yaml` referenciam essa imagem via `parent_image` + `skip_build: True`: o ZenML **não** a constrói para você — se mudar as dependências, reconstrua e envie a imagem novamente.

## 🚀 Executar o pipeline ETL no Vertex AI

Com o stack `gcp-stack` ativo:

```bash
poetry poe run-digital-data-etl-paul     # ou run-digital-data-etl para as duas fontes
```

Acompanhamento: console da GCP → **Vertex AI → Pipelines**, e o dashboard do ZenML Pro. Os documentos coletados ficam no Firestore (base `twin`).

Para depurar falhas: o estado real do job está na API do Vertex (`pipelineJobs`), e o erro concreto de um passo aparece no **Cloud Logging** (`gcloud logging read`) — o log local do ZenML apenas indica qual tarefa do DAG falhou, e seu "completed successfully" não é confiável.

## 🧪 Desenvolvimento local

O fluxo local continua funcionando (docker-compose com MongoDB + Qdrant e servidor ZenML local):

```bash
poetry poe local-infrastructure-up
poetry poe run-digital-data-etl
```

QA: `poetry poe lint-check`, `poetry poe format-check`, `poetry poe test`.

## 📄 Licença

Projeto sob licença MIT (ver `LICENSE`).
