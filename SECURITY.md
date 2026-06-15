# Security Policy

## Reporting a Vulnerability

If you find a security issue in CTFAgent, please report it privately. Do not open a public issue.

**Preferred channel:** Open a GitHub Security Advisory at [github.com/humaidhahm/ctfagent/security/advisories/new](https://github.com/humaidhahm/ctfagent/security/advisories/new).

## What to Include

- Affected file or component (path or filename)
- Affected version
- Reproduction steps
- Observed impact
- Any suggested fix

## What We Commit To

- Acknowledge receipt within 3 business days
- Initial triage within 7 business days
- Coordinated disclosure window of up to 90 days for confirmed vulnerabilities
- Credit in the changelog if desired

## Scope

**In scope:**
- Backend agent code (`backend/`)
- CLI client (`cli/`)
- API routes (`backend/api/`)
- Configuration and settings

**Out of scope:**
- Third-party tools the agents drive (sqlmap, pwntools, etc.) — report upstream
- NVIDIA NIM API infrastructure
- Theoretical issues without reproduction
