@echo off
REM Simple script to log in to Meta Ads MCP on Windows

SET APP_ID=%1

IF "%APP_ID%"=="" (
    IF NOT "%META_APP_ID%"=="" (
        SET APP_ID=%META_APP_ID%
    ) ELSE (
        echo Error: No Meta App ID provided.
        echo Usage: login.bat YOUR_APP_ID
        echo    or set the META_APP_ID environment variable.
        exit /b 1
    )
)

echo Starting Meta Ads authentication with App ID: %APP_ID%
python meta_ads_generated.py --login --app-id "%APP_ID%" 