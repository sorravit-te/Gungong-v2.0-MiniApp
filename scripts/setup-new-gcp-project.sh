#!/bin/bash

# ========================================
# GunGong - GCP Project Setup Script
# ========================================
# สคริปต์สำหรับสร้าง GCP Project ใหม่และ configuration ทั้งหมด

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Check if gcloud is installed
check_gcloud() {
    if ! command -v gcloud &> /dev/null; then
        print_error "gcloud CLI is not installed!"
        print_info "Install from: https://cloud.google.com/sdk/docs/install"
        exit 1
    fi
    print_success "gcloud CLI is installed"
}

# ========================================
# Main Script
# ========================================

print_header "GunGong GCP Project Setup"

# Check prerequisites
check_gcloud

# ========================================
# Step 1: Project Information
# ========================================
print_header "Step 1: Project Information"

echo -e "${YELLOW}Enter new GCP Project details:${NC}"
read -p "Project ID (or press Enter for auto-generated): " PROJECT_ID

if [ -z "$PROJECT_ID" ]; then
    PROJECT_ID="gungong-$(date +%s)"
    print_info "Generated Project ID: $PROJECT_ID"
fi

read -p "Project Name (default: GunGong Fraud Detection): " PROJECT_NAME
PROJECT_NAME=${PROJECT_NAME:-"GunGong Fraud Detection"}

# ========================================
# Step 2: Create GCP Project
# ========================================
print_header "Step 2: Creating GCP Project"

print_info "Creating project: $PROJECT_ID..."
if gcloud projects create "$PROJECT_ID" --name="$PROJECT_NAME" --set-as-default; then
    print_success "Project created successfully"
    echo "$PROJECT_ID" > .gcp-project-id
else
    print_error "Failed to create project"
    exit 1
fi

# ========================================
# Step 3: Link Billing Account
# ========================================
print_header "Step 3: Link Billing Account"

print_info "Available billing accounts:"
gcloud billing accounts list

echo ""
read -p "Enter Billing Account ID: " BILLING_ACCOUNT_ID

if [ -n "$BILLING_ACCOUNT_ID" ]; then
    print_info "Linking billing account..."
    if gcloud billing projects link "$PROJECT_ID" --billing-account="$BILLING_ACCOUNT_ID"; then
        print_success "Billing account linked"
    else
        print_warning "Failed to link billing account - you may need to do this manually"
    fi
else
    print_warning "Skipping billing account - you need to link it manually later"
fi

# ========================================
# Step 4: Enable APIs
# ========================================
print_header "Step 4: Enabling Required APIs"

APIS=(
    "cloudbuild.googleapis.com"
    "run.googleapis.com"
    "firestore.googleapis.com"
    "cloudresourcemanager.googleapis.com"
    "secretmanager.googleapis.com"
    "aiplatform.googleapis.com"
    "artifactregistry.googleapis.com"
)

for api in "${APIS[@]}"; do
    print_info "Enabling $api..."
    gcloud services enable "$api" --project="$PROJECT_ID"
done

print_success "All APIs enabled"

# ========================================
# Step 5: Create Firestore Database
# ========================================
print_header "Step 5: Creating Firestore Database"

read -p "Create Firestore database in asia-southeast1? (y/n): " CREATE_FIRESTORE

if [ "$CREATE_FIRESTORE" = "y" ] || [ "$CREATE_FIRESTORE" = "Y" ]; then
    print_info "Creating Firestore database..."
    if gcloud firestore databases create \
        --location=asia-southeast1 \
        --type=firestore-native \
        --project="$PROJECT_ID"; then
        print_success "Firestore database created"
    else
        print_warning "Firestore creation failed or already exists"
    fi
else
    print_warning "Skipping Firestore creation"
fi

# ========================================
# Step 6: Create Service Account
# ========================================
print_header "Step 6: Creating Service Account"

SERVICE_ACCOUNT_NAME="gungong-backend"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

print_info "Creating service account: $SERVICE_ACCOUNT_NAME..."
if gcloud iam service-accounts create "$SERVICE_ACCOUNT_NAME" \
    --display-name="GunGong Backend Service" \
    --description="Service account for GunGong backend application" \
    --project="$PROJECT_ID"; then
    print_success "Service account created"
else
    print_warning "Service account creation failed or already exists"
fi

# ========================================
# Step 7: Grant Permissions
# ========================================
print_header "Step 7: Granting Permissions"

ROLES=(
    "roles/datastore.user"
    "roles/storage.objectViewer"
    "roles/run.invoker"
    "roles/aiplatform.user"
)

for role in "${ROLES[@]}"; do
    print_info "Granting $role..."
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
        --role="$role" \
        --quiet
done

print_success "Permissions granted"

# ========================================
# Step 8: Create Service Account Key
# ========================================
print_header "Step 8: Creating Service Account Key"

mkdir -p secrets

print_info "Creating service account key..."
if gcloud iam service-accounts keys create secrets/service-account.json \
    --iam-account="$SERVICE_ACCOUNT_EMAIL" \
    --project="$PROJECT_ID"; then
    chmod 600 secrets/service-account.json
    print_success "Service account key created: secrets/service-account.json"
else
    print_error "Failed to create service account key"
    exit 1
fi

# ========================================
# Step 9: Create .env File
# ========================================
print_header "Step 9: Creating .env File"

print_info "Creating .env from template..."

cat > .env.new << EOF
# ========================================
# GunGong Configuration
# Generated on: $(date)
# ========================================

# Google Cloud & AI Configuration
GOOGLE_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.0-flash-exp
GOOGLE_APPLICATION_CREDENTIALS=secrets/service-account.json
FIRESTORE_PROJECT_ID=$PROJECT_ID

# LINE Bot Configuration
LINE_CHANNEL_ACCESS_TOKEN=your_line_channel_access_token
LINE_CHANNEL_SECRET=your_line_channel_secret

# Application Settings
APP_NAME=GunGong (กันโกง)
DEBUG=False
HOST=0.0.0.0
PORT=8000

# ngrok Configuration (Optional)
NGROK_AUTHTOKEN=your_ngrok_authtoken_here

# VirusTotal API (Optional)
VIRUSTOTAL_API_KEY=your_virustotal_api_key_here

# Firebase Emulator Settings
USE_FIREBASE_EMULATOR=false
EOF

print_success "Created .env.new file"
print_warning "Please review and rename .env.new to .env, then update API keys!"

# ========================================
# Step 10: Summary
# ========================================
print_header "Setup Complete! 🎉"

echo ""
echo -e "${GREEN}Project Details:${NC}"
echo -e "  Project ID: ${BLUE}$PROJECT_ID${NC}"
echo -e "  Project Name: ${BLUE}$PROJECT_NAME${NC}"
echo -e "  Service Account: ${BLUE}$SERVICE_ACCOUNT_EMAIL${NC}"
echo -e "  Region: ${BLUE}asia-southeast1${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "  1. Review and rename .env.new to .env"
echo "  2. Update API keys in .env file:"
echo "     - GOOGLE_API_KEY (Gemini)"
echo "     - LINE_CHANNEL_ACCESS_TOKEN"
echo "     - LINE_CHANNEL_SECRET"
echo "     - VIRUSTOTAL_API_KEY (optional)"
echo "  3. Deploy Firestore rules:"
echo "     firebase deploy --only firestore:rules --project=$PROJECT_ID"
echo "  4. Deploy to Cloud Run:"
echo "     gcloud builds submit --config=deployment/cloudbuild.yaml"
echo "  5. Update LINE Webhook URL"
echo ""
echo -e "${BLUE}Useful Commands:${NC}"
echo "  # Check project"
echo "  gcloud config get-value project"
echo ""
echo "  # Test Firestore access"
echo "  python scripts/test-firestore.py"
echo ""
echo "  # Deploy to Cloud Run"
echo "  gcloud builds submit --config=deployment/cloudbuild.yaml"
echo ""
echo -e "${GREEN}Setup completed successfully!${NC}"
echo ""

# Save setup info
cat > .gcp-setup-info.txt << EOF
GCP Setup Information
=====================
Date: $(date)
Project ID: $PROJECT_ID
Project Name: $PROJECT_NAME
Service Account: $SERVICE_ACCOUNT_EMAIL
Region: asia-southeast1
Firestore: Created (if selected)

Files Created:
- .gcp-project-id
- secrets/service-account.json
- .env.new

Next: Update .env.new with your API keys and rename to .env
EOF

print_success "Setup information saved to .gcp-setup-info.txt"
