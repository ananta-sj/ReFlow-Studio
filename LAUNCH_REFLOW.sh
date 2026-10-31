#!/bin/bash

# ======================================================
#    REFLOW STUDIO v0.6 (Ironclad) - Mac/Linux Launcher
# ======================================================

# 1. Ensure we are in the correct folder
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"
export PYTHONDONTWRITEBYTECODE=1

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}[INFO] Working Directory: $SCRIPT_DIR${NC}"

# 1b. Prefer the built native executable (packaging/build_dist.py /
# .github/workflows/build.yml) - if it's been built, it already bundles
# its own Python runtime and needs none of the steps below.
if [ -x "dist/ReflowStudio/ReflowStudio" ]; then
    echo -e "${GREEN}[INFO] Launching packaged build...${NC}"
    exec "./dist/ReflowStudio/ReflowStudio"
fi
echo -e "${CYAN}[INFO] No packaged build found (dist/ReflowStudio/ReflowStudio) - running from source.${NC}"

# 2. Setup/Locate Python Environment
# On Mac/Linux, we usually rely on a venv rather than a portable folder
if [ -d "python/bin" ]; then
    # Custom Portable Python folder found
    echo -e "${CYAN}[INFO] Using Portable Python folder...${NC}"
    PY="./python/bin/python3"
    export PATH="$SCRIPT_DIR/python/bin:$PATH"
elif [ -d "reflow_venv" ]; then
    # Existing Venv found
    echo -e "${CYAN}[INFO] Activating Virtual Environment...${NC}"
    source reflow_venv/bin/activate
    PY="python3"
else
    # Create new Venv if nothing exists
    echo -e "${CYAN}[INFO] Creating clean Python environment (First Run)...${NC}"
    python3 -m venv reflow_venv
    source reflow_venv/bin/activate
    PY="python3"
    # Upgrade pip immediately to avoid issues
    $PY -m pip install --upgrade pip

    # Install the full dependency list - core/integrity.py's self-healing
    # only covers a handful of critical libs, not everything pipeline.py
    # and its handlers import.
    if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
        echo -e "${CYAN}[INFO] Installing dependencies (this can take a while on first run)...${NC}"
        $PY -m pip install -r "$SCRIPT_DIR/requirements.txt"
    fi
fi

# 3. Setup FFmpeg
# If a local 'ffmpeg' folder exists (bundled binary), add it to path
if [ -d "ffmpeg/bin" ]; then
    echo -e "${CYAN}[INFO] Using local ffmpeg/bin folder for FFmpeg...${NC}"
    export PATH="$SCRIPT_DIR/ffmpeg/bin:$PATH"
elif [ -d "ffmpeg" ]; then
    echo -e "${CYAN}[INFO] Using local ffmpeg folder for FFmpeg...${NC}"
    export PATH="$SCRIPT_DIR/ffmpeg:$PATH"
fi

# Final check if FFmpeg is actually callable
if ! command -v ffmpeg &> /dev/null; then
    echo -e "${RED}[ERROR] FFmpeg is not found!${NC}"
    echo "        - Mac: Run 'brew install ffmpeg'"
    echo "        - Linux: Run 'sudo apt install ffmpeg'"
    exit 1
fi

# 4. RUN INTEGRITY GUARD (The Gatekeeper)
echo -e "\n${CYAN}[1/2] RUNNING INTEGRITY GUARD...${NC}"
$PY core/integrity.py

# Check if Integrity Guard failed
if [ $? -ne 0 ]; then
    echo -e "${RED}[CRITICAL] INTEGRITY CHECK FAILED.${NC}"
    echo "The app cannot start because libraries or models are missing."
    echo "Check the log messages above."
    exit 1
fi

# 5. VERIFY FRONTEND BUILD EXISTS
if [ ! -f "frontend/dist/index.html" ]; then
    echo -e "${RED}[CRITICAL] Frontend build not found at frontend/dist/index.html.${NC}"
    echo "This build is incomplete - the UI was never built."
    echo "If you are developing this app, run:"
    echo "    cd frontend && npm install && npm run build"
    exit 1
fi

# 6. LAUNCH APP
echo -e "\n${GREEN}[2/2] LAUNCHING REFLOW STUDIO...${NC}"
$PY main.py

# Deactivate venv on exit (if used)
if [ -n "$VIRTUAL_ENV" ]; then
    deactivate
fi