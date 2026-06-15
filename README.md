<div align="center">

# CTFAgent

**Autonomous Multi-Agent CTF Solver · LangGraph × NVIDIA NIM**

[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![LangGraph](https://img.shields.io/badge/LangGraph-✓-purple.svg)](https://langchain-ai.github.io/langgraph/)
[![Agents](https://img.shields.io/badge/Domain%20Agents-7-orange.svg)]()
[![Tools](https://img.shields.io/badge/Built--in%20Tools-28%2B-red.svg)]()
[![NVIDIA NIM](https://img.shields.io/badge/NVIDIA%20NIM-API-76B900.svg)](https://build.nvidia.com/)
[![PRs Welcome](https://img.shields.io/badge/PRs-Welcome-brightgreen.svg)](CONTRIBUTING.md)

[Quick Start](#quick-start) • [Architecture](#architecture) • [Usage](#usage) • [Tools](#tools-by-category) • [Installation](#installation) • [Contributing](#contributing)

</div>

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Usage](#usage)
- [Tools by Category](#tools-by-category)
- [Configuration](#configuration)
- [Docker](#docker)
- [Benchmarking](#benchmarking)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

CTFAgent is an **autonomous multi-agent framework** that solves Capture The Flag challenges across Web, Pwn, Reverse Engineering, Forensics, Crypto, OSINT, and Misc categories. It uses a **LangGraph state machine** to coordinate specialized LLM-powered agents, each equipped with domain-specific tools.

The supervisor classifies challenges, estimates difficulty, routes to domain specialists, and iterates until the flag is found — or all attempts are exhausted.

---

## Features

| Capability | Description |
|-----------|-------------|
| **Multi-Agent Architecture** | 7 specialized agents coordinated by a LangGraph supervisor with state persistence |
| **LLM-Powered Reasoning** | NVIDIA NIM API with automatic model selection, latency tracking, and rate-limit retry |
| **28+ Built-in Tools** | SQLMap, pwntools, binwalk, steghide, zsteg, ROPgadget, radare2, and more |
| **Experience Database** | Learns from past solves — similar challenges reuse proven workflows |
| **Session Persistence** | Maintains netcat/TCP sessions for interactive challenges |
| **RAG Knowledge Base** | Category-specific hacking guides (Web, Pwn, Forensics, Crypto, RE, OSINT) |
| **Auto-Setup** | One-command install of Python deps + system tools per domain |
| **Interactive CLI** | Metasploit-style console with solve, sessions, watch, writeup, benchmark commands |
| **Docker Support** | Containerized operation with docker-compose profiles |
| **Flag Detection** | Regex + LLM-based flag extraction and format validation |

---

## Architecture

```mermaid
flowchart LR
    classDef core fill:#1a2a4a,stroke:#5a7ab8,color:#eaf0ff
    classDef domain fill:#1a3a2a,stroke:#5ab87a,color:#eaffea
    classDef end fill:#3a1a1a,stroke:#b85a5a,color:#ffeaea

    CLI[CLI / API]:::core
    SUP[Supervisor]:::core
    CLS[Classifier]:::core
    DE[Difficulty Estimator]:::core
    FV[Flag Validator]:::core
    WEB[Web Agent]:::domain
    CRY[Crypto Agent]:::domain
    FOR[Forensics Agent]:::domain
    PWN[Pwn Agent]:::domain
    RE[RE Agent]:::domain
    MISC[Misc/OSINT Agent]:::domain
    ED[Experience DB]:::core
    SS[Session Store]:::core

    CLI --> SUP
    SUP --> CLS --> DE --> SUP
    SUP --> WEB & CRY & FOR & PWN & RE & MISC
    WEB & CRY & FOR & PWN & RE & MISC --> SUP
    SUP --> FV
    ED -.-> CLS
    ED -.-> WEB & CRY & FOR & PWN & RE & MISC
    SS -.-> CLI
```

### Components

| Component | File | Role |
|-----------|------|------|
| **Supervisor** | `backend/agents/supervisor.py` | Builds the LangGraph state graph, coordinates all agents, manages iteration loop |
| **Classifier** | `backend/agents/classifier.py` | Identifies challenge category from description + attachments using LLM |
| **Domain Agent** | `backend/agents/domain_agent.py` | Generic agent runner: calls LLM, parses tool calls, normalizes args, detects flags |
| **Tool Registry** | `backend/agents/tool_registry.py` | Maps tool names to implementations |
| **Experience DB** | `backend/memory/experience_db.py` | JSON-based database of past solves with similarity search |
| **Session Store** | `backend/memory/session_store.py` | Persistent session state with TTL-based eviction |
| **NIM Client** | `backend/core/nim_client.py` | OpenAI-compatible wrapper for NVIDIA NIM with latency tracking |
| **Flag Detector** | `backend/core/flag_detector.py` | Regex + LLM-based flag extraction and validation |
| **Ingestor** | `backend/ingestion/ingestor.py` | Parses challenge input, extracts files, creates manifest |
| **Smart Decode** | `backend/core/smart_decode.py` | Auto-detects and decodes various encodings |

---

## Quick Start

```bash
git clone https://github.com/humaidhahm/ctfagent.git
cd ctfagent
python3 run.py
```

On first run, the installer will:
1. Create a Python virtual environment
2. Install all Python dependencies
3. Install missing system tools (requires sudo)
4. Prompt for your NVIDIA NIM API key
5. Launch the interactive CLI

---

## Installation

### Prerequisites

- **Python 3.8+** — [python.org](https://python.org)
- **Linux** (recommended) or WSL2 on Windows
- **NVIDIA NIM API key** — free at [build.nvidia.com](https://build.nvidia.com/)
- **sudo access** — for system tool installation

### One-Command Install

```bash
git clone https://github.com/humaidhahm/ctfagent.git
cd ctfagent
python3 run.py
```

### Docker

```bash
docker compose --profile cli up -d     # CLI mode
docker compose --profile api up -d     # API server mode
```

### Manual Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API key
python -m cli.client
```

---

## Usage

### Interactive CLI

```
┃ ctfagent > help
```

| Command | Description |
|---------|-------------|
| `solve <description>` | Submit a CTF challenge to solve |
| `solve ./challenge.elf` | Solve from a challenge file |
| `sessions` | List all active sessions |
| `view <id>` | View session details and event trace |
| `watch <id>` | Live-stream agent reasoning trace |
| `writeup <id>` | Generate markdown writeup for solved challenge |
| `benchmark` | Run benchmark against known challenges |
| `experience` | View/manage experience database |
| `experience find <query>` | Search similar past challenges |
| `tools` | Check all available security tools |
| `install` | Install missing system tools (sudo) |
| `help` | Show help message |

### Solve Mode

```
┃ ctfagent > solve "The challenge has a login form at http://target.com with SQL injection in the username field"
```

The agent will:
1. Classify the challenge → **web**
2. Estimate difficulty
3. Route to the **Web Agent**
4. Iteratively select and run tools (sqlmap, curl_probe, etc.)
5. Detect and validate the flag
6. Save to the experience database

### Hint Mode

Get a progressive hint without spoiling the solution:

```
The agent will generate a single progressive hint based on the challenge context.
```

---

## Tools by Category

### Web
| Tool | Description |
|------|-------------|
| sqlmap | Automated SQL injection detection and exploitation |
| ffuf | Fast web fuzzer for content discovery |
| gobuster | Directory/file enumeration |
| curl_probe | Custom HTTP probing with header analysis |

### Forensics
| Tool | Description |
|------|-------------|
| binwalk | Firmware analysis and file carving |
| exiftool | Metadata extraction from files |
| steghide | JPEG/BMP/WAV steganography |
| zsteg | PNG/BMP LSB stego detection |
| tshark | Network packet analysis |
| file_decoder | Multi-format file decoder |
| foremost | File carving and recovery |

### Pwn
| Tool | Description |
|------|-------------|
| pwntools | CTF binary exploitation framework |
| checksec | Binary security check |
| ROPgadget | ROP gadget finder |
| remote_connect | TCP session manager |
| heartbleed | Heartbleed vulnerability checker |

### Reverse Engineering
| Tool | Description |
|------|-------------|
| radare2 | Binary analysis framework |
| strings | Extract readable strings from binaries |

### Crypto
| Tool | Description |
|------|-------------|
| cipher_cracker | Classical and modern cipher analysis |
| rsa_solver | RSA parameter recovery (Wiener, Hastad, etc.) |
| encoding_detector | Auto-detect encoding schemes (base64, hex, etc.) |

### OSINT
| Tool | Description |
|------|-------------|
| password_profiler | Generate password profiles from personal data |
| cupp | Common User Passwords Profiler |

### General
| Tool | Description |
|------|-------------|
| download_file | Download files from URLs |
| file_reader | Read and analyze files |
| binary_calc | Binary/hex/decimal calculator |

---

## Configuration

Copy `.env.example` to `.env`:

```ini
# ─── Required ────────────────────────────────────────────────
NVIDIA_NIM_API_KEY=your_key_here
NVIDIA_NIM_BASE_URL=https://integrate.api.nvidia.com/v1

# ─── Agent Configuration ────────────────────────────────────
MAX_AGENT_ITERATIONS=20
MAX_TOOL_TIMEOUT_SECONDS=300
AGENT_TEMPERATURE=0.1

# ─── CTF Flag ──────────────────────────────────────────────
FLAG_FORMAT=picoCTF
```

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `NVIDIA_NIM_API_KEY` | Yes | — | NVIDIA NIM API key |
| `NVIDIA_NIM_BASE_URL` | No | `https://integrate.api.nvidia.com/v1` | NIM API base URL |
| `MAX_AGENT_ITERATIONS` | No | 20 | Max solve iterations |
| `AGENT_TEMPERATURE` | No | 0.1 | LLM temperature |
| `FLAG_FORMAT` | No | — | Flag prefix regex pattern |
| `API_HOST` | No | `0.0.0.0` | API server host |
| `API_PORT` | No | 8000 | API server port |

---

## Docker

```bash
# Build and run CLI
docker compose --profile cli up -d

# Build and run API server
docker compose --profile api up -d

# Attach to CLI container
docker attach ctfagent
```

The Docker image includes: sqlmap, gobuster, ffuf, binwalk, exiftool, steghide, tshark, foremost, hashcat, john, and all Python dependencies.

---

## Benchmarking

```bash
# Run from CLI
benchmark

# Or directly
python benchmark_models.py
python quick_bench.py
```

---

## Project Structure

```
ctfagent/
├── backend/
│   ├── agents/           # Supervisor, classifier, domain agents
│   │   ├── supervisor.py # LangGraph state machine coordinator
│   │   ├── classifier.py # Challenge category classifier
│   │   ├── domain_agent.py # Generic agent runner
│   │   ├── web_agent.py
│   │   ├── pwn_agent.py
│   │   ├── re_agent.py
│   │   ├── crypto_agent.py
│   │   ├── forensics_agent.py
│   │   └── misc_agent.py
│   ├── core/             # LLM client, state, flag detection
│   ├── tools/            # 28+ domain-specific tools
│   ├── memory/           # Experience DB, session store
│   ├── ingestion/        # Challenge file ingestion
│   ├── config/           # Settings & environment
│   ├── api/              # FastAPI server & websocket
│   └── schemas/          # Pydantic models
├── cli/                  # Interactive Metasploit-style console
├── rag_knowledge/        # Category-specific knowledge base
├── tests/                # Unit tests
└── data/                 # Runtime data (sessions, experience)
```

---

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

[MIT License](LICENSE) — Copyright (c) 2026 CTFAgent

---

<div align="center">

Built with [LangGraph](https://langchain-ai.github.io/langgraph/) and [NVIDIA NIM](https://build.nvidia.com/)

</div>
