# Cloud Run Deployment Guide for gitdevcards

## Quick Start (Recommended)

Deploy your FastAPI application to Cloud Run with a single command:

```bash
export PROJECT_ID=your-gcp-project-id
export REGION=us-central1

gcloud run deploy gitdevcards \
  --source . \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 1 \
  --max-instances 100
```

After deployment, your app will be available at:
```
https://gitdevcards-<random-id>.<region>.run.app
```

---

## 3 Deployment Options

### Option 1: Source-Based Deployment (Fastest)
`gcloud run deploy` automatically builds and deploys from your source code:
```bash
gcloud run deploy gitdevcards \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

**Pros:** Simple, fast, automatic Docker building
**Cons:** Less control over build process

---

### Option 2: Cloud Build with CI/CD (Recommended for Teams)

1. **Enable Cloud Build API:**
```bash
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
```

2. **Connect GitHub repository:**
```bash
gcloud builds connect --repo-name=gitdevcards --repo-owner=mamta072703
```

3. **Create a build trigger:**
```bash
gcloud builds triggers create github \
  --repo-name=gitdevcards \
  --repo-owner=mamta072703 \
  --branch-pattern='^main$' \
  --build-config=cloudbuild.yaml \
  --name=gitdevcards-trigger
```

4. **Push to main branch to auto-deploy:**
```bash
git push origin main
```

**Pros:** Automated CI/CD, audit trail, team-friendly
**Cons:** More setup required

---

### Option 3: Manual Docker Build & Push

1. **Build Docker image:**
```bash
export PROJECT_ID=your-gcp-project-id
docker build -t gcr.io/$PROJECT_ID/gitdevcards:latest .
```

2. **Push to Container Registry:**
```bash
docker push gcr.io/$PROJECT_ID/gitdevcards:latest
```

3. **Deploy from image:**
```bash
gcloud run deploy gitdevcards \
  --image gcr.io/$PROJECT_ID/gitdevcards:latest \
  --platform managed \
  --region us-central1 \
  --memory 2Gi \
  --cpu 1
```

**Pros:** Full control, local testing
**Cons:** Manual process

---

## Environment Variables

Your app reads the `PORT` environment variable (default: 8080). Cloud Run automatically sets this.

To add custom environment variables:

```bash
gcloud run deploy gitdevcards \
  --source . \
  --set-env-vars="CUSTOM_VAR=value,ANOTHER_VAR=another_value"
```

---

## Monitoring & Logs

### View logs:
```bash
gcloud run logs read gitdevcards --limit 50
```

### Stream logs in real-time:
```bash
gcloud run logs read gitdevcards --limit 50 --follow
```

### View in Cloud Console:
```
https://console.cloud.google.com/run/detail/<region>/gitdevcards
```

---

## Scaling Configuration

Current settings in `service.yaml`:
- **Min instances:** 1
- **Max instances:** 100
- **Target CPU utilization:** 70%
- **Memory:** 2Gi
- **CPU:** 1 vCPU

To update scaling:
```bash
gcloud run services update gitdevcards \
  --min-instances 1 \
  --max-instances 50 \
  --region us-central1
```

---

## Testing the Deployment

1. **Health check:**
```bash
curl https://gitdevcards-xxxxx.us-central1.run.app/health
```

Expected response:
```json
{"status":"ok"}
```

2. **Generate a card:**
```bash
curl -X POST https://gitdevcards-xxxxx.us-central1.run.app/generate \
  -H "Content-Type: application/json" \
  -d '{"username":"octocat"}'
```

3. **Serve a card:**
```bash
curl https://gitdevcards-xxxxx.us-central1.run.app/card/octocat
```

---

## Troubleshooting

### Service won't start
- Check logs: `gcloud run logs read gitdevcards --limit 100`
- Verify PORT environment variable is 8080
- Ensure health check endpoint `/health` is working

### High memory usage
- Check application logs for memory leaks
- Reduce `--max-instances` if costs are high
- Enable **Cloud Profiler** for detailed analysis

### Timeout errors
- Increase request timeout: `--timeout=3600s`
- Check if agent operations are timing out
- Consider async processing for long operations

### Authentication errors
- For public API: use `--allow-unauthenticated`
- For private API: use IAM roles or API keys
- View permissions: `gcloud run services get-iam-policy gitdevcards`

---

## Security Best Practices

1. **Disable public access (if not needed):**
```bash
gcloud run services remove-iam-policy-binding gitdevcards \
  --member=allUsers \
  --role=roles/run.invoker
```

2. **Restrict to specific users/services:**
```bash
gcloud run services add-iam-policy-binding gitdevcards \
  --member=user:your-email@example.com \
  --role=roles/run.invoker
```

3. **Enable VPC Connector for private database access:**
```bash
gcloud run deploy gitdevcards \
  --vpc-connector=my-connector \
  --vpc-egress=private-ranges-only
```

---

## Cost Estimation

Cloud Run pricing (as of 2026):
- **Compute:** $0.00001667/vCPU-second
- **Memory:** $0.00000417/GB-second
- **Requests:** $0.40 per 1M requests
- **First 2M requests/month:** Free

**Example monthly cost (minimal traffic):**
- 1,000 requests/month @ 2Gi, 1 vCPU, 30s avg: ~$0.50

---

## Updating Your Deployment

### After code changes:
```bash
git add .
git commit -m "Update feature"
git push origin main
```

If using Cloud Build trigger, deployment happens automatically.

For manual deployment:
```bash
gcloud run deploy gitdevcards --source .
```

---

## Useful Commands

```bash
# View service details
gcloud run services describe gitdevcards --region us-central1

# List all Cloud Run services
gcloud run services list

# Delete service
gcloud run services delete gitdevcards --region us-central1

# View revisions
gcloud run revisions list --service gitdevcards

# Set traffic split (for canary deployments)
gcloud run services update-traffic gitdevcards --to-revisions LATEST=100
```

---

## Support & Resources

- **Cloud Run Docs:** https://cloud.google.com/run/docs
- **FastAPI Docs:** https://fastapi.tiangolo.com
- **Cloud Build Docs:** https://cloud.google.com/build/docs
- **Pricing Calculator:** https://cloud.google.com/products/calculator

---

**Last Updated:** 2026-05-20
**Status:** Ready for deployment ✅
