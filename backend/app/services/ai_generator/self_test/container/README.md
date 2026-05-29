# XSS Self-Test Container

Headless-Chromium (Playwright) service that verifies a generated XSS task is
genuinely solvable before the pipeline publishes it.

## What it checks

| Signal | Meaning |
|---|---|
| `executed` | Injecting `payload_solution` into the vulnerable param fires JS (alert or `window.__xss_fired`) |
| `flag_reachable` | After execution, `document.cookie` contains the flag |
| `baseline_safe` | Loading the page *without* the payload does NOT fire XSS |

All three must be true for the variant to pass the `SOLVABILITY` binary gate.

## Build

```bash
cd backend/app/services/ai_generator/self_test/container
docker build -t xss-selftest:latest .
```

## Run locally (for testing)

```bash
docker run --rm -p 8080:8080 xss-selftest:latest
# Health check
curl http://localhost:8080/health
# Test (replace html/payload with real values)
curl -X POST http://localhost:8080/selftest \
  -H "Content-Type: application/json" \
  -d '{"html":"<html>...</html>","xss_type":"reflected","vulnerable_param":"q","payload_solution":"<img src=x onerror=alert(1)>","flag":"CTF{test}"}'
```

## Deploy to Yandex Serverless Containers

1. Push image to Yandex Container Registry:
```bash
YC_REGISTRY=cr.yandex/<REGISTRY_ID>
docker tag xss-selftest:latest $YC_REGISTRY/xss-selftest:latest
docker push $YC_REGISTRY/xss-selftest:latest
```

2. Create / update the serverless container:
```bash
yc serverless container revision deploy \
  --container-name xss-selftest \
  --image $YC_REGISTRY/xss-selftest:latest \
  --cores 1 \
  --memory 1GB \
  --concurrency 1 \
  --execution-timeout 30s \
  --service-account-id <SA_ID>
```

3. Restrict invocation to backend service account only:
```bash
yc serverless container allow-unauthenticated-invoke --name xss-selftest --no-allow
yc serverless container add-access-binding \
  --name xss-selftest \
  --role serverless.containers.invoker \
  --service-account-id <BACKEND_SA_ID>
```

4. Set backend env vars:
```
AI_GEN_ENABLE_SELFTEST=true
AI_GEN_SELFTEST_URL=https://<container-id>.containers.yandexcloud.net
AI_GEN_SELFTEST_TIMEOUT_S=20
```

5. Optionally set `YANDEX_IAM_TOKEN` or rely on instance metadata (prod only).

## Notes

- Container needs no outbound internet: HTML is passed inline via `data:` URI.
- Single worker (`--workers 1`) — Playwright browser is single-threaded; Yandex
  Serverless Containers handle parallelism by running multiple container instances.
- Concurrency=1 per container instance ensures one Playwright context at a time.
- Memory 1GB minimum for Chromium.
