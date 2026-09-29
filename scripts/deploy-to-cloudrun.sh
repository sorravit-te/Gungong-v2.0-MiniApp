#!/bin/bash

# ========================================
# GunGong - Cloud Run Deployment Script
# Full-Stack (Frontend + Backend)
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

print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }

# ========================================
# Check Prerequisites
# ========================================
print_header "GunGong Deployment to Cloud Run"

if ! command -v gcloud &> /dev/null; then
    print_error "gcloud CLI not installed!"
    exit 1
fi

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ]; then
    print_error "No GCP project selected!"
    echo "Run: gcloud config set project YOUR_PROJECT_ID"
    exit 1
fi

print_info "Project: $PROJECT_ID"
print_info "Region: asia-southeast1"

# ========================================
# Confirm Deployment
# ========================================
echo ""
read -p "Deploy to Cloud Run? This will build and deploy the full-stack app. (y/n): " CONFIRM

if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
    print_warning "Deployment cancelled"
    exit 0
fi

# ========================================
# Deploy with Cloud Build
# ========================================
print_header "Building and Deploying"

print_info "Starting Cloud Build..."
print_warning "This may take 10-15 minutes (building frontend + backend + Playwright)"

if gcloud builds submit \
    --config=deployment/cloudbuild-fullstack.yaml \
    --timeout=40m \
    .; then
    print_success "Deployment successful!"
else
    print_error "Deployment failed!"
    exit 1
fi

# ========================================
# Get Service URL
# ========================================
print_header "Deployment Complete"

SERVICE_URL=$(gcloud run services describe gungong-fullstack \
    --region=asia-southeast1 \
    --format='value(status.url)' 2>/dev/null)

if [ -n "$SERVICE_URL" ]; then
    echo ""
    echo -e "${GREEN}🎉 Deployment successful!${NC}"
    echo ""
    echo -e "${BLUE}Service URL:${NC} $SERVICE_URL"
    echo ""
    echo -e "${YELLOW}Next Steps:${NC}"
    echo "  1. Update LINE Webhook URL to: $SERVICE_URL/webhook"
    echo "  2. Test frontend at: $SERVICE_URL"
    echo "  3. Check health: $SERVICE_URL/health"
    echo ""
    echo -e "${BLUE}Useful Commands:${NC}"
    echo "  # View logs"
    echo "  gcloud run services logs read gungong-fullstack --region=asia-southeast1"
    echo ""
    echo "  # Update service"
    echo "  ./scripts/deploy-to-cloudrun.sh"
    echo ""
else
    print_error "Could not get service URL"
fi
