## What Was Generated
A production‑ready GitHub Actions workflow (`ci-cd.yml`) that builds a Docker image, pushes it to GitHub Container Registry, pulls environment secrets from Infisical, and deploys the new image to a Kubernetes cluster. A concise setup‑guide (`setup-guide.md`) lists required secrets, one‑time cluster setup, and how to start the pipeline.

## Prerequisites
- **Runner OS**: `ubuntu-latest` (GitHub‑hosted).  
- **GitHub Actions versions**:  
  - `actions/checkout@v4`  
  - `docker/setup-qemu-action@v3`  
  - `docker/setup-buildx-action@v3`  
  - `docker/login-action@v3`  
  - `docker/build-push-action@v5`  
  - `azure/setup-kubectl@v4` (k8s `v1.28.0`)  
  - `supplypike/setup-infisical@v1`  
- **Infisical CLI**: latest (installed by the action).  

## Step‑by‑Step Implementation
1. **Add workflow file**  
   ```bash
   mkdir -p .github/workflows
   cat > .github/workflows/ci-cd.yml <<'EOF'
   # (content from ci-cd.yml)
   EOF
   git add .github/workflows/ci-cd.yml
   ```
2. **Add the setup guide** (optional, for documentation)  
   ```bash
   cat > setup-guide.md <<'EOF'
   # (content from setup-guide.md)
   EOF
   git add setup-guide.md
   ```
3. **Commit and push**  
   ```bash
   git commit -m "Add CI/CD GitHub Actions workflow"
   git push origin main
   ```
4. **Create required GitHub secrets** (via UI or CLI):  
   ```bash
   gh secret set INFISICAL_TOKEN --repo Navneet072300/RunBookIQ --body "<your-token>"
   gh secret set KUBE_CONFIG --repo Navneet072300/RunBookIQ --body "$(base64 -w0 path/to/kubeconfig)"
   ```
5. **Verify deployment** – after the pipeline finishes, run:  
   ```bash
   kubectl get deployment runbookiq -n <namespace>
   kubectl describe deployment runbookiq
   ```

## Verify It Worked
- **Image in GHCR**  
  ```bash
  gh api -H "Accept: application/vnd.github+json" \
      /repos/Navneet072300/RunBookIQ/packages/container/RunBookIQ/versions \
      --jq '.[0].metadata.container.tags'
  ```
- **Kubernetes rollout**  
  ```bash
  kubectl get pods -l app=runbookiq
  kubectl rollout status deployment/runbookiq
  ```

## Troubleshooting
| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| `failed to solve: failed to copy: httpReadSeeker: failed to copy ... unauthorized: authentication required` | GHCR login failed | Ensure `GITHUB_TOKEN` has `write:packages` permission (default for actions) and the repository is not in a private organization that blocks token usage. |
| `infisical: command not found` or `INFISICAL_TOKEN secret not set` | Infisical CLI step couldn't read the token | Verify `INFISICAL_TOKEN` secret exists and is correct; re‑run the workflow. |
| `error: unable to decode kubeconfig` | `KUBE_CONFIG` not valid base64 or corrupted | Re‑encode the kubeconfig: `base64 -w0 path/to/kubeconfig` and update the secret. |
| `deployment.apps "runbookiq" not found` | Kubernetes namespace or deployment name mismatch | Confirm the deployment exists (`kubectl get deployments`) and adjust the name in the workflow if needed. |
| `rollout status timed out` | New pods failing to start (e.g., image pull error) | Check pod logs: `kubectl logs -l app=runbookiq` and ensure the image tag exists in GHCR. |
--- END ---