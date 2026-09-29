#!/bin/bash

# ========================================
# Deploy GunGong to Cloud Run
# ========================================

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# ========================================
# Load Configuration
# ========================================
print_header "GunGong Cloud Run Deployment"

# Load .env file
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
    print_success "Loaded .env file"
else
    print_error ".env file not found!"
    print_info "Please create .env file first"
    exit 1
fi

# Get Project ID
if [ -f .gcp-project-id ]; then
    PROJECT_ID=$(cat .gcp-project-id)
    print_info "Using Project ID from .gcp-project-id: $PROJECT_ID"
else
    PROJECT_ID="${FIRESTORE_PROJECT_ID}"
    print_warning "Using Project ID from .env: $PROJECT_ID"
fi

# Check if PROJECT_ID is set
if [ -z "$PROJECT_ID" ]; then
    print_error "PROJECT_ID not set!"
    exit 1
fi

# Configuration
REGION="${REGION:-asia-southeast1}"
SERVICE_NAME="${SERVICE_NAME:-gungong}"
MEMORY="${MEMORY:-2Gi}"
CPU="${CPU:-2}"
MAX_INSTANCES="${MAX_INSTANCES:-10}"
TIMEOUT="${TIMEOUT:-300}"

print_info "Configuration:"
echo "  Project ID: $PROJECT_ID"
echo "  Service Name: $SERVICE_NAME"
echo "  Region: $REGION"
echo "  Memory: $MEMORY"
echo "  CPU: $CPU"
echo "  Max Instances: $MAX_INSTANCES"
echo ""

# ========================================
# Step 1: Set Active Project
# ========================================
print_header "Step 1: Setting Active Project"

gcloud config set project "$PROJECT_ID"
print_success "Project set to $PROJECT_ID"

# ========================================
# Step 2: Build & Submit
# ========================================
print_header "Step 2: Building and Pushing Image"

read -p "Use Cloud Build? (y/n, default: y): " USE_CLOUD_BUILD
USE_CLOUD_BUILD=${USE_CLOUD_BUILD:-y}

if [ "$USE_CLOUD_BUILD" = "y" ] || [ "$USE_CLOUD_BUILD" = "Y" ]; then
    print_info "Building with Cloud Build..."

    if [ -f deployment/cloudbuild.yaml ]; then
        gcloud builds submit --config=deployment/cloudbuild.yaml
    else
        gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME
    fi

    print_success "Build completed"
else
    print_info "Building locally with Docker..."

    # Build locally
    docker build -t gcr.io/$PROJECT_ID/$SERVICE_NAME .

    # Push to GCR
    docker push gcr.io/$PROJECT_ID/$SERVICE_NAME

    print_success "Image pushed to GCR"
fi

# ========================================
# Step 3: Deploy to Cloud Run
# ========================================
print_header "Step 3: Deploying to Cloud Run"

# Check if we should update existing service or create new
SERVICE_EXISTS=$(gcloud run services list --platform managed --region $REGION --filter="metadata.name:$SERVICE_NAME" --format="value(metadata.name)" 2>/dev/null || echo "")

if [ -n "$SERVICE_EXISTS" ]; then
    print_info "Service '$SERVICE_NAME' exists. Updating..."
    ACTION="update"
else
    print_info "Creating new service '$SERVICE_NAME'..."
    ACTION="create"
fi

# Get service account
SERVICE_ACCOUNT=$(gcloud iam service-accounts list --filter="displayName:GunGong Backend Service" --format="value(email)" 2>/dev/null || echo "")

if [ -z "$SERVICE_ACCOUNT" ]; then
    print_warning "Service account not found. Using default compute service account"
    SERVICE_ACCOUNT_ARG=""
else
    print_info "Using service account: $SERVICE_ACCOUNT"
    SERVICE_ACCOUNT_ARG="--service-account=$SERVICE_ACCOUNT"
fi

# Deploy
print_info "Deploying..."

gcloud run deploy $SERVICE_NAME \
    --image gcr.io/$PROJECT_ID/$SERVICE_NAME:latest \
    --region $REGION \
    --platform managed \
    --allow-unauthenticated \
    --memory $MEMORY \
    --cpu $CPU \
    --max-instances $MAX_INSTANCES \
    --timeout $TIMEOUT \
    --port 8080 \
    $SERVICE_ACCOUNT_ARG \
    --set-env-vars "FIRESTORE_PROJECT_ID=$FIRESTORE_PROJECT_ID,GEMINI_MODEL=$GEMINI_MODEL,APP_NAME=$APP_NAME,DEBUG=$DEBUG,USE_FIREBASE_EMULATOR=false" \
    --set-secrets "GOOGLE_API_KEY=GOOGLE_API_KEY:latest,LINE_CHANNEL_ACCESS_TOKEN=LINE_CHANNEL_ACCESS_TOKEN:latest,LINE_CHANNEL_SECRET=LINE_CHANNEL_SECRET:latest" 2>/dev/null || \
gcloud run deploy $SERVICE_NAME \
    --image gcr.io/$PROJECT_ID/$SERVICE_NAME:latest \
    --region $REGION \
    --platform managed \
    --allow-unauthenticated \
    --memory $MEMORY \
    --cpu $CPU \
    --max-instances $MAX_INSTANCES \
    --timeout $TIMEOUT \
    --port 8080 \
    $SERVICE_ACCOUNT_ARG \
    --update-env-vars "FIRESTORE_PROJECT_ID=$FIRESTORE_PROJECT_ID,GEMINI_MODEL=$GEMINI_MODEL,APP_NAME=$APP_NAME,DEBUG=$DEBUG,USE_FIREBASE_EMULATOR=false,GOOGLE_API_KEY=$GOOGLE_API_KEY,LINE_CHANNEL_ACCESS_TOKEN=$LINE_CHANNEL_ACCESS_TOKEN,LINE_CHANNEL_SECRET=$LINE_CHANNEL_SECRET"

print_success "Deployment completed"

# ========================================
# Step 4: Get Service URL
# ========================================
print_header "Step 4: Service Information"

SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
    --region $REGION \
    --platform managed \
    --format 'value(status.url)')

print_success "Service deployed successfully!"
echo ""
echo -e "${GREEN}Service URL: ${BLUE}$SERVICE_URL${NC}"
echo ""

# Save URL
echo "$SERVICE_URL" > .cloud-run-url

# ========================================
# Step 5: Test Deployment
# ========================================
print_header "Step 5: Testing Deployment"

print_info "Testing health endpoint..."
if curl -s -f "${SERVICE_URL}/health" > /dev/null; then
    print_success "Health check passed"
    echo ""
    echo "Response:"
    curl -s "${SERVICE_URL}/health" | python3 -m json.tool || curl -s "${SERVICE_URL}/health"
else
    print_warning "Health check failed - service may still be starting up"
fi

# ========================================
# Summary
# ========================================
print_header "Deployment Summary"

echo ""
echo -e "${GREEN}✅ Deployment Complete!${NC}"
echo ""
echo -e "${BLUE}Service Details:${NC}"
echo "  Name: $SERVICE_NAME"
echo "  URL: $SERVICE_URL"
echo "  Region: $REGION"
echo "  Project: $PROJECT_ID"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "  1. Update LINE Webhook URL:"
echo "     ${SERVICE_URL}/webhook"
echo ""
echo "  2. Test the API:"
echo "     curl ${SERVICE_URL}/health"
echo ""
echo "  3. View logs:"
echo "     gcloud run services logs read $SERVICE_NAME --region $REGION"
echo ""
echo "  4. Update service (after code changes):"
echo "     ./scripts/deploy-to-cloud-run.sh"
echo ""

# Save deployment info
cat > .deployment-info.txt << EOF
Deployment Information
======================
Date: $(date)
Project ID: $PROJECT_ID
Service Name: $SERVICE_NAME
Service URL: $SERVICE_URL
Region: $REGION
Image: gcr.io/$PROJECT_ID/$SERVICE_NAME:latest

Configuration:
- Memory: $MEMORY
- CPU: $CPU
- Max Instances: $MAX_INSTANCES
- Timeout: ${TIMEOUT}s

Next Steps:
1. Update LINE Webhook URL: ${SERVICE_URL}/webhook
2. Test API: curl ${SERVICE_URL}/health
3. View logs: gcloud run services logs read $SERVICE_NAME --region $REGION
EOF

print_success "Deployment info saved to .deployment-info.txt"
