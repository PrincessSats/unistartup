# XSS Self-Test Container — Yandex Cloud Deploy Guide

Headless Chromium (Playwright) service that proves generated XSS tasks actually work
before the pipeline publishes them. Runs as a Yandex Serverless Container.

## Prerequisites

```bash
# yc CLI
curl -sSL https://storage.yandexcloud.net/yandexcloud-yc/install.sh | bash
yc init   # login, pick the hacknet folder

# confirm active folder
yc config list
```

---

## Step 1 — Container Registry (one-time)

```bash
yc container registry create --name hacknet-registry
# save the registry ID, e.g. crp1234abcd
REGISTRY_ID=crp1234abcd
```

---

## Step 2 — Service accounts (one-time)

```bash
# SA the container RUNS AS (no special roles needed — no outbound calls)
yc iam service-account create --name hacknet-selftest-sa

# SA the BACKEND uses to CALL the container
# reuse existing backend SA if one already exists
yc iam service-account create --name hacknet-backend-sa
```

---

## Step 3 — Build and push image

```bash
cd backend/app/services/ai_generator/self_test/container

REGISTRY_ID=crp1234abcd          # from step 1
# Yandex registry format: cr.yandex/<REGISTRY_ID>/<image>:<tag>
# (registry ID is a PATH segment, NOT a subdomain)
IMAGE=cr.yandex/$REGISTRY_ID/xss-selftest:latest

yc container registry configure-docker   # auth Docker to YC registry

# Yandex Serverless Containers run linux/amd64 ONLY and reject buildx manifest
# lists / attestation. On Apple Silicon (arm64) you MUST cross-build for amd64
# and disable provenance/sbom, otherwise deploy fails with an opaque
# "Internal error". --push builds + pushes a single-platform image in one step.
docker buildx build \
  --platform linux/amd64 \
  --provenance=false \
  --sbom=false \
  -t $IMAGE \
  --push .
```

Verify the pushed image is a single amd64 manifest (no `image.index`, no
`attestation-manifest`):
```bash
docker buildx imagetools inspect $IMAGE
# Platform: linux/amd64   ← must be this, and ONLY this
```

---

## Step 4 — Deploy Serverless Container

```bash
SELFTEST_SA=$(yc iam service-account get hacknet-selftest-sa --format json | jq -r .id)

# REQUIRED: the container SA must be able to PULL the image from the registry,
# otherwise revision deploy fails with "Not enough permissions to use image".
yc container registry add-access-binding \
  --id $REGISTRY_ID \
  --role container-registry.images.puller \
  --service-account-id $SELFTEST_SA

yc serverless container create --name hacknet-xss-selftest

yc serverless container revision deploy \
  --container-name hacknet-xss-selftest \
  --image $IMAGE \
  --cores 1 \
  --memory 1GB \
  --concurrency 1 \
  --execution-timeout 30s \
  --service-account-id $SELFTEST_SA

# Get the HTTPS URL — paste it into .env as AI_GEN_SELFTEST_URL
yc serverless container get hacknet-xss-selftest --format json | jq -r .url
# → https://bba1234xxxxx.containers.yandexcloud.net
```

---

## Step 5 — IAM: let backend call the container

```bash
BACKEND_SA=$(yc iam service-account get hacknet-backend-sa --format json | jq -r .id)
CONTAINER_ID=$(yc serverless container get hacknet-xss-selftest --format json | jq -r .id)

# Block unauthenticated calls
yc serverless container deny-unauthenticated-invoke --name hacknet-xss-selftest

# Grant backend SA invoke rights
yc serverless container add-access-binding \
  --id $CONTAINER_ID \
  --role serverless.containers.invoker \
  --service-account-id $BACKEND_SA
```

---

## Step 6 — IAM token for the backend host

### Option A — Backend on Yandex Cloud VM / Container (production)
The `xss_selftest.py` client auto-fetches the IAM token from instance metadata
(`169.254.169.254`). No extra config needed — just ensure the VM/container runs
under the `hacknet-backend-sa` service account.

### Option B — Backend outside Yandex Cloud (dev / CI)
```bash
yc iam key create --service-account-name hacknet-backend-sa --output key.json
yc config set service-account-key key.json
yc iam create-token   # valid 12 h
```
Set in `.env`: `YANDEX_IAM_TOKEN=t1.9euelZ...`

---

## Step 7 — Backend environment variables

Add to `backend/.env` (never commit):

```env
# XSS Self-Test (Yandex Serverless Container)
AI_GEN_ENABLE_SELFTEST=true
AI_GEN_SELFTEST_URL=https://bba1234xxxxx.containers.yandexcloud.net
AI_GEN_SELFTEST_TIMEOUT_S=20

# Only needed when backend is NOT on a Yandex Cloud VM:
# YANDEX_IAM_TOKEN=t1.9euelZ...
```

**Default is `AI_GEN_ENABLE_SELFTEST=false`** — no behaviour change until you set it.
One flag activates the self-test for all three generation paths:
- Admin generate (`routes/ai_generate.py`)
- Daily cron (`daily_pipeline.py`)
- User variants (`routes/user_variants.py`)

---

## Step 8 — Smoke test

```bash
TOKEN=$(yc iam create-token)

# Health
curl https://bba1234xxxxx.containers.yandexcloud.net/health
# → {"status":"ok","browser":"ready"}

# Real test — should get executed=true, flag_reachable=true
curl -X POST https://bba1234xxxxx.containers.yandexcloud.net/selftest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "html": "<html><script>document.cookie=\"flag=CTF{test}\"; path=/</script><div id=r></div><script>var q=new URLSearchParams(location.search).get(\"q\");if(q)document.getElementById(\"r\").innerHTML=q;</script></html>",
    "xss_type": "reflected",
    "vulnerable_param": "q",
    "payload_solution": "<img src=x onerror=alert(document.cookie)>",
    "flag": "CTF{test}"
  }'
```

Expected response:
```json
{"executed": true, "flag_reachable": true, "baseline_safe": true, "detail": "..."}
```

---

## Step 9 — Update image (future deploys)

```bash
docker buildx build \
  --platform linux/amd64 --provenance=false --sbom=false \
  -t $IMAGE --push .

yc serverless container revision deploy \
  --container-name hacknet-xss-selftest \
  --image $IMAGE \
  --cores 1 \
  --memory 1GB \
  --concurrency 1 \
  --execution-timeout 30s \
  --service-account-id $SELFTEST_SA
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Not enough permissions to use image` (deploy) | Container SA missing registry pull role | Run the `add-access-binding ... container-registry.images.puller` in step 4; confirm with `list-access-bindings` |
| `Internal error` (deploy, opaque) | Image is arm64, or a buildx manifest list / attestation | Rebuild with `docker buildx build --platform linux/amd64 --provenance=false --sbom=false --push`; verify `imagetools inspect` shows only `linux/amd64` |
| `401 Unauthorized` | IAM token missing or expired | Re-run `yc iam create-token`, set `YANDEX_IAM_TOKEN` |
| `403 Forbidden` | Backend SA not in invoker binding | Re-run step 5 |
| `503 Service Unavailable` | Container cold-start or crashed | Check container logs: `yc serverless container logs --name hacknet-xss-selftest` |
| `executed=false` for valid payload | Playwright timeout | Increase `--execution-timeout` to 45s and `AI_GEN_SELFTEST_TIMEOUT_S=35` |
| Self-test not running in pipeline | Flag not set | Confirm `AI_GEN_ENABLE_SELFTEST=true` and `AI_GEN_SELFTEST_URL` is non-empty in backend env |
| Generation still works with bad URL | Correct — fail-open | Pipeline falls back to static heuristic on any container error; check logs for `XSS self-test fallback` |

---

## Notes

- Container needs **no outbound internet**: HTML is passed inline (data: URI). Network egress not required.
- Memory **1 GB minimum** for Chromium.
- `concurrency=1` per container instance — Yandex Serverless scales horizontal instances for parallelism.
- Self-test verdict persisted in `ai_generation_variants.reward_checks[SOLVABILITY].detail` — auditable in DB.
