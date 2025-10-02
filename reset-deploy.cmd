@echo off
REM =====================================================================
REM reset-deploy.cmd - Clean reset + redeploy for Transcribe App (Docker)
REM Stops/removes old container/image, pulls latest Git, rebuilds, runs.
REM =====================================================================
setlocal EnableExtensions EnableDelayedExpansion

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

REM --- Config (edit if needed) ---
set "CONTAINER_NAME=transcribe-1"
set "IMAGE_NAME=transcribe-app"
set "PORT=5000"
set "VOLUMES=-v "%CD%\uploads:/app/uploads""

echo [STEP] Stopping/removing old container (%CONTAINER_NAME%)...
docker stop %CONTAINER_NAME% 2>nul || echo [INFO] No running container.
docker rm %CONTAINER_NAME% 2>nul || echo [INFO] No existing container.

echo [STEP] Removing old image (%IMAGE_NAME%)...
docker rmi %IMAGE_NAME% 2>nul || echo [INFO] No image to remove.

echo [STEP] Pulling latest Git changes...
git pull origin main 2>nul || (
    echo [WARN] Git pull failed (not a repo? Skipping.)
)

echo [STEP] Rebuilding image (%IMAGE_NAME%)...
docker build -t %IMAGE_NAME% . --no-cache
if errorlevel 1 (
    echo [ERR] Build failed.
    pause
    exit /b 1
)

echo [STEP] Running new container (%CONTAINER_NAME%) on port %PORT%...
docker run -d -p %PORT%:5000 --name %CONTAINER_NAME% --restart=always %VOLUMES% %IMAGE_NAME%
if errorlevel 1 (
    echo [ERR] Run failed.
    pause
    exit /b 1
)

echo [OK] Reset complete! Access: http://localhost:%PORT%
docker logs %CONTAINER_NAME%

pause
