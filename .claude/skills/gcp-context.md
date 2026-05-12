# GCP Infrastructure Context
*Single source of truth for all cloud resources. Update immediately when anything is created.*
*Never hardcode these values in code — import from env vars or Secret Manager.*

---

## GCP project

| Key | Value |
|-----|-------|
| Project ID | ai-projects-494800 |
| Project name | ai-projects |
| Billing account | [UPDATE when created] |
| Region (default) | us-central1 |
| Zone (default) | us-central1-a |

**GCP free tier:** $300 credit. Track spend at console.cloud.google.com/billing.
Estimated monthly cost when all 5 projects are live: ~$15-40/mo (Cloud Run
scales to zero, Vertex AI charged per training job, Artifact Registry minimal).

---

## Artifact Registry

| Key | Value |
|-----|-------|
| Registry name | tutor-app |
| Registry URL | us-central1-docker.pkg.dev/ai-projects-494800/tutor-app |
| Repos | tutor-app, cloud-run-source-deploy |

**Push an image:**
```bash
gcloud auth configure-docker us-central1-docker.pkg.dev
docker tag IMAGE_NAME REGISTRY_URL/IMAGE_NAME:TAG
docker push REGISTRY_URL/IMAGE_NAME:TAG
```

---

## Cloud Run services

| Service | Project | URL | Status | Min instances |
|---------|---------|-----|--------|---------------|
| p1-tutor | P1 | https://tutor-app-474302100622.us-central1.run.app | 🟢 live | 0 |
| p3-analyzer | P3 | [UPDATE when deployed] | 🔴 not deployed | 0 |
| p3-xgboost-api | P3 | [UPDATE when deployed] | 🔴 not deployed | 0 |
| p4-optimizer | P4 | [UPDATE when deployed] | 🔴 not deployed | 0 |

**Deploy a Cloud Run service:**
```bash
gcloud run deploy SERVICE_NAME \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8080 \
  --set-secrets=OPENAI_API_KEY=OPENAI_API_KEY:latest
```

---

## Cloud Functions

| Function | Project | Trigger | Status |
|----------|---------|---------|--------|
| p2-intelligence-agent | P2 | HTTP (via Cloud Scheduler) | 🔴 not deployed |

---

## Cloud Scheduler jobs

| Job | Cron | Target | Status |
|-----|------|--------|--------|
| p2-weekly-briefing | 0 8 * * 1 (Mon 8am) | p2-intelligence-agent | 🔴 not created |

---

## Cloud Storage buckets

| Bucket | Purpose | Projects | Status |
|--------|---------|---------|--------|
| [UPDATE]-10k-filings | Store EDGAR 10-K PDFs | P3, P5 | 🔴 not created |
| [UPDATE]-model-artifacts | Store trained XGBoost + LSTM models | P3, P4 | 🔴 not created |

**Create a bucket:**
```bash
gcloud storage buckets create gs://BUCKET_NAME \
  --location=us-central1 \
  --uniform-bucket-level-access
```

**Upload a file:**
```bash
gcloud storage cp local_file.pdf gs://BUCKET_NAME/path/file.pdf
```

---

## Secret Manager secrets

| Secret name | What it stores | Projects that use it |
|-------------|---------------|---------------------|
| OPENAI_API_KEY | OpenAI API key | P1, P2, P3, P4, P5 |
| tavily-api-key | Tavily search API key | P2 |
| newsapi-key | NewsAPI key | P2 |
| sendgrid-api-key | SendGrid email (P2 briefing) | P2 |
| langsmith-api-key | LangSmith tracing | all projects |

**Create a secret:**
```bash
echo -n "your-api-key" | gcloud secrets create SECRET_NAME \
  --data-file=- \
  --replication-policy=automatic
```

**Access in Python:**
```python
from google.cloud import secretmanager
client = secretmanager.SecretManagerServiceClient()
name = f"projects/PROJECT_ID/secrets/SECRET_NAME/versions/latest"
response = client.access_secret_version(request={"name": name})
secret_value = response.payload.data.decode("UTF-8")
```

---

## Vertex AI

| Resource | Purpose | Status |
|----------|---------|--------|
| Vector Search index | P2 article embeddings | 🔴 not created |
| Custom training job | P4 LSTM training | 🔴 not submitted |
| Prediction endpoint | P4 LSTM inference | 🔴 not deployed |

**GCP ACE exam study mapping:**
- Month 1: Cloud Run, Artifact Registry, Secret Manager, IAM ← doing now
- Month 2: Cloud Functions, Cloud Scheduler, Pub/Sub, Vertex AI Vector Search
- Month 3: GCS, Cloud Run Jobs, XGBoost model serving
- Month 4: Vertex AI Training + Prediction, practice exams

---

## IAM & service accounts

| Service account | Roles | Used by |
|----------------|-------|---------|
| 474302100622-compute@developer.gserviceaccount.com | roles/artifactregistry.writer, roles/logging.logWriter, roles/storage.objectViewer, roles/secretmanager.secretAccessor | Cloud Run services |
| 474302100622@cloudbuild.gserviceaccount.com | roles/storage.admin, roles/artifactregistry.writer | Cloud Build |

**Principle of least privilege:** each service gets only the roles it needs.
Do not use owner/editor roles for deployed services.

---

## Local development setup

```bash
# Authenticate locally
gcloud auth application-default login

# Set project
gcloud config set project PROJECT_ID

# Run Cloud Run service locally with env vars
docker run -p 8080:8080 \
  -e GOOGLE_CLOUD_PROJECT=PROJECT_ID \
  IMAGE_NAME
```

**.env file for local dev (never commit this):**
```
OPENAI_API_KEY=sk-...
TAVILY_API_KEY=tvly-...
LANGCHAIN_API_KEY=ls-...
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=caiya-ai-projects
GCP_PROJECT_ID=...
GCS_BUCKET_10K=...
GCS_BUCKET_MODELS=...
```
