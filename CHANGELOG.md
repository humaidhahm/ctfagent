# Changelog

All notable changes to CTFAgent are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versioning follows [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-06-15

### Added
- **Multi-agent architecture** with LangGraph state machine coordinating 7 domain agents
- **LLM-powered reasoning** via NVIDIA NIM API with automatic model selection and latency tracking
- **Classifier** that identifies challenge category from description + attachments
- **Difficulty estimator** that predicts solve time based on challenge context
- **7 domain agents**: Web, Pwn, Reverse Engineering, Forensics, Crypto, OSINT/Misc
- **28+ built-in tools** organized by domain: sqlmap, pwntools, binwalk, steghide, zsteg, ROPgadget, radare2, and more
- **Experience database** with TF-IDF similarity search for reusing past solve workflows
- **Session store** with TTL-based eviction and persistent state
- **Interactive CLI** with Metasploit-style console (solve, sessions, view, watch, writeup, tools)
- **Flag detection** with regex + LLM-based extraction and format validation
- **RAG knowledge base** with category-specific hacking guides
- **Auto-installer** that sets up Python deps + system tools by domain
- **Docker support** with docker-compose profiles (CLI + API)
- **REST API** with FastAPI, websocket support, and CORS configuration
- **Smart argument normalization** for LLM-generated tool calls
- **Loop detection** to prevent repeated failed tool attempts
- **Model registry** with tier-based selection (fast/capable/unreliable)
- **Rate-limit handling** with exponential backoff for LLM calls
- **Comprehensive documentation**: README, INSTALL, CHANGELOG, SECURITY, DISCLAIMER, CONTRIBUTING
- **GitHub templates**: issue templates, Dependabot config, CODEOWNERS, .gitattributes
- **doctor.sh**: tool installation audit script
- **Claude Code agent definitions** in `.claude/agents/`

### Architecture
```
CLI/API → Supervisor → Classifier → Difficulty Estimator → Domain Agents → Flag Validator
           ↑_______________ iterative loop _______________↓
```
