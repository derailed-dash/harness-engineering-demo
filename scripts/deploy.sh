#!/usr/bin/env bash
# Deployment script for Harness Engineering Workbench to Google Cloud Run

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

SERVICE_NAME="harness-engineering-demo"
REGION="${GCP_REGION:-us-central1}"
MODEL_NAME="${MODEL_NAME:-gemini-3.8-flash}"

echo "==========================================================="
echo " Deploying Harness Engineering Demo to Google Cloud Run"
echo " Service:  ${SERVICE_NAME}"
echo " Region:   ${REGION}"
echo " Model:    ${MODEL_NAME}"
echo "==========================================================="

# Check that gcloud is authenticated
if ! gcloud auth print-identity-token &>/dev/null; then
    echo "Error: gcloud is not authenticated. Please run 'gcloud auth login'."
    exit 1
fi

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
    echo "Error: No active GCP project configured. Run 'gcloud config set project <PROJECT_ID>'."
    exit 1
fi

echo "Active Project: ${PROJECT_ID}"

# Deploy directly via source build
gcloud run deploy "${SERVICE_NAME}" \
    --source "${PROJECT_ROOT}" \
    --region "${REGION}" \
    --allow-unauthenticated \
    --set-env-vars "MODEL_NAME=${MODEL_NAME}" \
    --port 8080

echo ""
echo "Deployment successful!"
gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --format="value(status.url)"
