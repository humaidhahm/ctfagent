# CTFAgent

AI-powered multi-agent CTF solver that autonomously solves Capture The Flag challenges across multiple categories: Web, Pwn, Reverse Engineering, Forensics, Crypto, OSINT, and General Skills.

## Features

- **Multi-agent architecture** — specialized agents for each CTF domain, coordinated by a supervisor
- **LLM-powered reasoning** — uses NVIDIA NIM API for AI reasoning with automatic model selection
- **Session persistence** — maintains netcat/TCP sessions for interactive challenges
- **Experience database** — learns from past solves; workflows are reused on similar challenges
- **28+ built-in tools** — SQLMap, Gobuster, pwntools, binwalk, steghide, zsteg, ROPgadget, and more
- **Automatic setup** — installs system tools and Python dependencies by domain
- **RAG knowledge base** — category-specific hacking guides included

## Quick Start

### Docker (recommended for macOS and Windows without WSL/Linux)

Use Docker if you are on macOS, on Windows without WSL2, or on a system where installing Linux CTF tools directly is inconvenient. The Docker image includes the Debian/apt-based tools that CTFAgent needs, including tools such as SQLMap, Gobuster, ffuf, binwalk, steghide, tshark, pwntools, ROPgadget, and zsteg.

Install Docker Desktop first:

- macOS: install Docker Desktop for Mac
- Windows without WSL/Linux: install Docker Desktop for Windows and run these commands from PowerShell, Windows Terminal, Git Bash, or another terminal with Docker available

Then run CTFAgent:

```bash
git clone https://github.com/yourusername/ctfagent.git
cd ctfagent
mkdir -p data uploads
DOCKER_BUILDKIT=1 docker build -t ctfagent .
docker compose run --rm ctfagent
```

The Dockerfile uses BuildKit cache mounts for pip, so unchanged Python packages are reused across rebuilds when BuildKit is enabled. The first interactive Docker run prompts for your API keys/provider and writes configuration to `data/.env`. Compose mounts that file into the container, so your setup persists across container rebuilds and restarts.

To run the CLI again later:

```bash
docker compose run --rm ctfagent
```

To start the API after completing the interactive CLI setup:

```bash
docker compose --profile api up
```

Then open:

```text
http://localhost:8000/docs
```

The API service uses a Compose profile, so `docker compose up` by itself will not start it. Use `--profile api` for the API server.

### Native Linux / WSL

Use the native installer if you are on Linux or WSL2 and want CTFAgent installed directly on that environment.

```bash
git clone https://github.com/humaidhahm/ctfagent
cd ctfagent
python3 run.py
```

On first run, the installer will:
1. Create a Python virtual environment (`.venv`) — this avoids the *"externally-managed-environment"* error on newer Debian/Ubuntu releases that block system-wide `pip` installs
2. Install all Python dependencies inside the virtual environment
3. Install missing system tools (requires sudo)
4. Prompt you for your NVIDIA NIM API key
5. Launch the interactive CLI

> **Note:** If your system Python lacks `venv` support, install it first: `sudo apt install python3-venv`

## Requirements

- **Docker Desktop** for macOS, Windows without WSL/Linux, and non-Debian systems
- **Python 3.8+** for native Linux/WSL installs
- **Linux** or WSL2 for native installs
- **NVIDIA NIM API key** — get one free at [build.nvidia.com](https://build.nvidia.com/)
- **sudo access** for native system tool installation

## Usage

The CLI supports two modes:

### Solve Mode
```
Enter the challenge description, paste a URL, or upload a file.
The agent will classify the challenge, select the right tools, and work through it step by step.
```

### Hint Mode
```
Get a progressive hint without spoiling the full solution.
```

### Commands

| Command | Description |
|---------|-------------|
| `help` | Show help message |
| `install` | Re-run system tool installation |
| `tools` | List all available solving tools |
| `stats` | Show experience database stats |
| `history` | Show past solved challenges |
| `session` | Show active netcat sessions |
| `clear` | Clear the screen |
| `exit` / `quit` | Exit |

## Architecture

```
CLI (cli/client.py)
  └── Supervisor (backend/agents/supervisor.py)
        ├── Classifier — identifies challenge category
        ├── Difficulty Estimator — estimates solve time
        ├── Domain Agents:
        │     ├── Web Agent
        │     ├── Pwn Agent
        │     ├── RE Agent
        │     ├── Forensics Agent
        │     ├── Crypto Agent
        │     ├── OSINT/Misc Agent
        └── Flag Validator — detects and validates flags
```

## Tools by Category

**Web:** sqlmap, ffuf, curl_probe, gobuster
**Forensics:** binwalk, exiftool, steghide, zsteg, tshark, file_decoder, foremost
**Pwn:** pwntools, checksec, ROPgadget, remote_connect, heartbleed
**RE:** radare2, strings
**Crypto:** cipher_cracker, rsa_solver, encoding_detector
**OSINT:** password_profiler, cupp
**General:** download_file, file_reader, binary_calc

## Configuration

Native setup writes `.env` in the project root. Docker setup writes `data/.env` so configuration persists across container rebuilds and recreations.

For the Docker interactive CLI, attach stdin and a TTY:

```bash
docker compose run --rm ctfagent
```

You can also copy `.env.example` to the relevant env file and configure it manually:

| Variable | Required | Description |
|----------|----------|-------------|
| `LLM_PROVIDER` | Yes | `nim`, `gemma`, or `gemini` |
| `NVIDIA_NIM_API_KEYS` | For NIM | Comma-separated NVIDIA NIM API keys |
| `NVIDIA_NIM_BASE_URL` | No | Base URL for NIM API |
| `GOOGLE_API_KEYS` | For Gemma/Gemini | Comma-separated Google AI API keys |
| `GOOGLE_MIN_REQUEST_INTERVAL_SECONDS` | No | Delay between Google LLM requests (default: 1.0) |
| `MAX_AGENT_ITERATIONS` | No | Max solve attempts (default: 20) |
| `FLAG_FORMAT` | No | Flag prefix (e.g. picoCTF, CTF) |

Gemini/Gemma rate limits are quota-based at the Google project level. Multiple
keys from the same project share that quota; use `/llm` to reconfigure keys and
check the configured key count shown at startup. If your keys are from the same
project, increase `GOOGLE_MIN_REQUEST_INTERVAL_SECONDS` to avoid shared quota
bursts.

## License

MIT
