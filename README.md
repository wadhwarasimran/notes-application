# notes-application — the code

This repo holds **what to build**: the app, its Dockerfile, and the pipeline that publishes it.
It is one half of a two-repo CI/CD setup — the other half is **`notes-gitops`**, which holds
**what to run**.

```
you push code  →  CI: build → smoke-test → push ghcr.io/<you>/notes-api:<sha>
               →  CI writes that tag into notes-gitops
               →  Argo CD syncs your cluster
```

## What the pipeline does (`.github/workflows/ci.yml`)

1. **Build** the image, tagged twice: the commit **SHA** (immutable — exactly this code) and `latest`
   (a moving pointer you never deploy).
2. **Smoke-test it** — start the container and check `/healthz` and `/ready` answer. This is a **gate**:
   if it fails, nothing is published.
3. **Push** both tags to GHCR.
4. **Write the new tag into `notes-gitops`** — *this is the deploy.*

Notice what's missing: **this workflow never talks to Kubernetes and holds no cluster credentials.**
It only writes to Git. The cluster pulls from there itself.

## Setup

You need one secret, because `GITHUB_TOKEN` can only write to *this* repo:

- **`GITOPS_TOKEN`** — a fine-grained PAT with **Contents: Read and write** on your `notes-gitops`
  repo only. Add it under *Settings → Secrets and variables → Actions*.

Full steps are in the parent `README.md`.

## Run it locally

```bash
pip install -r requirements.txt
python app/app.py
curl localhost:8080/          # the greeting
curl localhost:8080/healthz   # ok
curl localhost:8080/ready     # ready
```
