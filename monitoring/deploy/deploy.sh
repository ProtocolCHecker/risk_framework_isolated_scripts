#!/bin/bash
#
# Risk Monitoring System - AWS Deployment Script
#
# Prerequisites:
#   - AWS CLI configured with appropriate credentials
#   - SAM CLI installed (pip install aws-sam-cli)
#   - Docker installed (for building Lambda layers)
#
# Usage:
#   ./deploy.sh [environment]
#
#   environment: production (default) or staging
#
# First-time deployment:
#   ./deploy.sh --guided
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MONITORING_DIR="$(dirname "$SCRIPT_DIR")"

# Default environment
ENVIRONMENT="${1:-production}"

echo "=========================================="
echo "Risk Monitoring System - AWS Deployment"
echo "=========================================="
echo "Environment: $ENVIRONMENT"
echo "Directory: $MONITORING_DIR"
echo ""

# Check prerequisites
command -v sam >/dev/null 2>&1 || { echo "ERROR: SAM CLI not installed. Run: pip install aws-sam-cli"; exit 1; }
command -v aws >/dev/null 2>&1 || { echo "ERROR: AWS CLI not installed."; exit 1; }

# Navigate to monitoring directory
cd "$MONITORING_DIR"

# Build the application
echo "Building Lambda functions..."
sam build -t deploy/template.yaml

# Deploy based on arguments
if [[ "$1" == "--guided" ]]; then
    echo ""
    echo "Running guided deployment..."
    echo "You will be prompted for parameter values."
    echo ""
    sam deploy --guided
else
    echo ""
    echo "Deploying to $ENVIRONMENT..."
    sam deploy --config-env "$ENVIRONMENT"
fi

echo ""
echo "=========================================="
echo "Deployment complete!"
echo "=========================================="
echo ""
echo "To view logs:"
echo "  aws logs tail /aws/lambda/risk-monitoring-critical-$ENVIRONMENT --follow"
echo ""
echo "To invoke manually:"
echo "  aws lambda invoke --function-name risk-monitoring-critical-$ENVIRONMENT output.json"
echo ""
