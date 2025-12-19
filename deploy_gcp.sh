#!/bin/bash

# Configuration
PROJECT_ID="uncanny-backend" # Replace with your actual Project ID
APP_NAME="uncanny-mixer"
REGION="us-central1"

# Ensure we are in the script's directory
cd "$(dirname "$0")" || exit

echo "--- Preparing Build Context ---"
# Clean up any previous artifacts
rm -rf ./temp_inf

# Exit on error
set -e

# We rely on './inf' being present in the current directory (User manual copy)
if [ ! -d "./inf" ]; then
    echo "Error: ./inf directory not found! Please ensure models are present locally."
    exit 1
fi
# No copy needed, Dockerfile copies ./inf directly

# Artifact Registry Target (Matches Cloud Run's default source-deploy repo)
IMAGE_TAG="us-central1-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/$APP_NAME"

echo "--- Building Container (Timeout: 2h) ---"
# We specifically use a 2h timeout because the first CUDA build is massive/slow.
gcloud builds submit --project $PROJECT_ID --region $REGION --tag $IMAGE_TAG --timeout=2h .

echo "--- Deploying Service 1: uncanny-mixer (PRO) ---"
gcloud run deploy $APP_NAME \
  --project $PROJECT_ID \
  --quiet \
  --image $IMAGE_TAG \
  --region $REGION \
  --env-vars-file env_vars_pro.yaml \
  --memory 16Gi \
  --cpu 4 \
  --gpu 1 \
  --gpu-type nvidia-l4 \
  --no-gpu-zonal-redundancy \
  --no-cpu-throttling \
  --execution-environment gen2 \
  --max-instances 1 \
  --clear-volume-mounts \
  --timeout 3600

# IAM Configuration: PUBLIC Access (App handles Auth)
# We must allow allUsers so the browser can load the page to show the login screen.
echo "--- Configuring Public Access for PRO Service (App-Level Auth) ---"
gcloud run services add-iam-policy-binding $APP_NAME \
  --project $PROJECT_ID \
  --region $REGION \
  --member="allUsers" \
  --role="roles/run.invoker"

# Remove legacy manual allowlist users (Cleanup)
echo "--- Cleaning up legacy IAM bindings ---"
gcloud run services remove-iam-policy-binding $APP_NAME \
  --project $PROJECT_ID \
  --region $REGION \
  --member="user:domo@lign.dev" \
  --role="roles/run.invoker" > /dev/null 2>&1 || true

gcloud run services remove-iam-policy-binding $APP_NAME \
  --project $PROJECT_ID \
  --region $REGION \
  --member="user:smithmail@gmail.com" \
  --role="roles/run.invoker" > /dev/null 2>&1 || true

echo "--- Deploying Service 2: uncanny-mixer-free (FREE) ---"
echo "--- Resetting FREE Tier Service (Deleting to clear stuck GPU config) ---"
# We delete the service to ensure a fresh start without inherited GPU matching errors
gcloud run services delete "${APP_NAME}-free" --region $REGION --quiet || echo "Service did not exist, nothing to delete."

# Note: We are using CPU-only for Free Tier because requesting a 2nd GPU triggered "Rate Exceeded" (HTTP 429) errors,
# indicating physical resource contention/stockout despite logical quota.
gcloud run deploy "${APP_NAME}-free" \
  --project $PROJECT_ID \
  --quiet \
  --image $IMAGE_TAG \
  --region $REGION \
  --allow-unauthenticated \
  --set-env-vars TIER=FREE \
  --memory 4Gi \
  --cpu 2 \
  --max-instances 1 \
  --timeout 3600
  # Disabled for 503 fix:
  # --add-volume=name=wav_storage,type=cloud-storage,bucket=uncanny-mixer-wav-storage \
  # --add-volume-mount=volume=wav_storage,mount-path=/tmp/wavF \

echo "--- Cleanup ---"
# No temp_inf to clean

echo "Done! App should be live."
