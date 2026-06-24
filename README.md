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
docker compose --profile cli run --rm ctfagent
```

The first interactive Docker run prompts for your API keys/provider and writes configuration to `data/.env`. That file is mounted into the container, so your setup persists across container rebuilds and restarts.

To run the CLI again later:

```bash
docker compose --profile cli run --rm ctfagent
```

To start the API after completing the interactive CLI setup:

```bash
docker compose --profile api up
```

Then open:

```text
http://localhost:8000/docs
```

Both Docker services use Compose profiles, so `docker compose up` by itself will not start CTFAgent. Use `--profile cli` for the interactive solver or `--profile api` for the API server.

### Native Linux / WSL

Use the native installer if you are on Linux or WSL2 and want CTFAgent installed directly on that environment.

```bash
git clone https://github.com/yourusername/ctfagent.git
cd ctfagent
python3 run.py
```

On first run, the installer will:
1. Create a Python virtual environment
2. Install all Python dependencies
3. Install missing system tools (requires sudo)
4. Prompt you for your NVIDIA NIM API key
5. Launch the interactive CLI

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

You can also copy `.env.example` to the relevant env file and configure it manually:

| Variable | Required | Description |
|----------|----------|-------------|
| `NVIDIA_NIM_API_KEY` | Yes | NVIDIA NIM API key |
| `NVIDIA_NIM_BASE_URL` | No | Base URL for NIM API |
| `MAX_AGENT_ITERATIONS` | No | Max solve attempts (default: 20) |
| `FLAG_FORMAT` | No | Flag prefix (e.g. picoCTF, CTF) |

## License

MIT
