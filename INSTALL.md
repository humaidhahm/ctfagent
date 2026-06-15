# Installation Guide

## Prerequisites

- **Python 3.8+** — [Download Python](https://python.org/downloads/)
- **Linux** (recommended) or **WSL2** on Windows
- **NVIDIA NIM API Key** — Get one free at [build.nvidia.com](https://build.nvidia.com/)
- **sudo access** — Required for system tool installation

## Quick Install (Recommended)

```bash
git clone https://github.com/humaidhahm/ctfagent.git
cd ctfagent
python3 run.py
```

The auto-installer will:
1. Check Python version
2. Create a virtual environment (`.venv/`)
3. Install all Python dependencies from `requirements.txt`
4. Install missing system tools by domain
5. Prompt for your NVIDIA NIM API key
6. Launch the interactive CLI

## Manual Install

### Step 1: Clone and Setup

```bash
git clone https://github.com/humaidhahm/ctfagent.git
cd ctfagent
python3 -m venv .venv
source .venv/bin/activate
```

### Step 2: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 3: Configure Environment

```bash
cp .env.example .env
# Edit .env with your NVIDIA NIM API key
```

### Step 4: Install System Tools (Optional)

```bash
# Run the installer for system tools
python3 run.py --install-only
```

Or install domain-specific tools manually:

**Web:** `sudo apt install sqlmap gobuster ffuf nikto whatweb`
**Forensics:** `sudo apt install binwalk exiftool steghide tshark foremost`
**Pwn:** `sudo apt install gdb binutils patchelf`
**RE:** `sudo apt install radare2 upx-ucl`
**Crypto:** `sudo apt install openssl hashid`
**OSINT:** `sudo apt install whois dnsutils`

### Step 5: Launch

```bash
python -m cli.client
```

## Docker Installation

```bash
# Build the image
docker compose build

# Run CLI mode
docker compose --profile cli up -d
docker attach ctfagent

# Or run API server mode
docker compose --profile api up -d
```

## API Server

```bash
# Start the FastAPI server
python -m backend.main

# API available at http://localhost:8000
# Docs at http://localhost:8000/docs
```

## Verification

```bash
# Start the CLI
python -m cli.client

# Check tools
┃ ctfagent > tools

# Try a benchmark
┃ ctfagent > benchmark
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Python 3.8+ required` | Install Python 3.8 or later |
| `NVIDIA_NIM_API_KEY not set` | Edit `.env` and add your key |
| `sudo: not found` | Run as root or install sudo |
| `ModuleNotFoundError` | Ensure virtual environment is activated |
| `Tool not found` | Run `install` from the CLI or install manually |
| Docker permission denied | Add user to docker group: `sudo usermod -aG docker $USER` |

## Tool Audit

Check which tools are available on your system:

```bash
bash db/doctor.sh
```
