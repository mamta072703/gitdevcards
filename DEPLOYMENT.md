# Quick Deployment Reference

## One-Command Deploy to Cloud Run

```bash
gcloud run deploy gitdevcards \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 1 \
  --max-instances 100
```

**Service URL:** `https://gitdevcards-xxxxx.us-central1.run.app`

---

## Test the Service

```bash
# Health check
curl https://gitdevcards-xxxxx.us-central1.run.app/health

# Generate card
curl -X POST https://gitdevcards-xxxxx.us-central1.run.app/generate \
  -H "Content-Type: application/json" \
  -d '{"username":"octocat"}'
```

---

## View Logs

```bash
gcloud run logs read gitdevcards --limit 50
```

---

📖 See **CLOUD_RUN_DEPLOYMENT.md** for comprehensive guide with:
- 3 deployment methods
- CI/CD setup with Cloud Build
- Scaling & monitoring
- Troubleshooting
- Security best practices
- Cost estimation
