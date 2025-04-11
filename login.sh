#!/bin/bash
# Simple script to log in to Meta Ads MCP

# Check for app ID in argument or environment variable
if [ "$1" != "" ]; then
    APP_ID="$1"
elif [ "$META_APP_ID" != "" ]; then
    APP_ID="$META_APP_ID"
else
    echo "Error: No Meta App ID provided."
    echo "Usage: ./login.sh YOUR_APP_ID"
    echo "   or set the META_APP_ID environment variable."
    exit 1
fi

echo "Starting Meta Ads authentication with App ID: $APP_ID"
python meta_ads_generated.py --login --app-id "$APP_ID" 