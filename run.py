#!/usr/bin/env python3
"""
CTFAgent — Autonomous Multi-Agent CTF Solver
Single-file auto-installer + launcher.

Run: python3 run.py

This will:
  1. Check Python version
  2. Create & activate a virtual environment (if needed)
  3. Install/update all Python dependencies
  4. Install missing system tools by domain (Web, Pwn, Forensics, RE, Crypto, OSINT)
  5. Create .env configuration
  6. Verify everything works
  7. Launch the interactive CLI
"""

import os
import sys
import subprocess
import shutil
import textwrap
from pathlib import Path

# ─── ANSI Colors ───────────────────────────────────────────
class C:
    BOLD = '\033[1m'
    DIM = '\033[2m'
    GREEN = '\033[0;32m'
    BRIGHT_GREEN = '\033[1;32m'
    CYAN = '\033[0;36m'
    BRIGHT_CYAN = '\033[1;36m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    BLUE = '\033[0;34m'
    MAGENTA = '\033[0;35m'
    ORANGE = '\033[0;33m'
    WHITE = '\033[1;37m'
    NC = '\033[0m'
    CHECK = f'{GREEN}✔{NC}'
    CROSS = f'{RED}✘{NC}'
    ARROW = f'{CYAN}▸{NC}'

DOMAIN_COLORS = {
    'Web': C.CYAN, 'Forensics': C.BLUE, 'Pwn': C.RED,
    'RE': C.MAGENTA, 'Crypto': C.YELLOW, 'OSINT': C.ORANGE, 'Misc': C.GREEN,
}

BASE_DIR = Path(__file__).parent.resolve()
VENV_DIR = BASE_DIR / '.venv'
REQUIREMENTS = BASE_DIR / 'requirements.txt'
ENV_FILE = Path(os.environ.get('CTFAGENT_ENV_FILE', BASE_DIR / '.env')).expanduser()
ENV_EXAMPLE = BASE_DIR / '.env.example'

# ─── Tool Database ─────────────────────────────────────────
# (domain, binary_name, apt_package, pip_package, verify_import)
#
# Special install methods (handled in install_system_tools):
#   If an entry has pip_package="gem:xxx", it's installed via `gem install xxx`.

TOOLS = [
    # Web
    ('Web', 'sqlmap', 'sqlmap', None, None),
    ('Web', 'gobuster', 'gobuster', None, None),
    ('Web', 'ffuf', 'ffuf', None, None),
    ('Web', 'nikto', 'nikto', None, None),
    ('Web', 'whatweb', 'whatweb', None, None),
    ('Web', 'wfuzz', 'wfuzz', None, None),
    ('Web', 'nmap', 'nmap', None, None),
    ('Web', 'nc', 'netcat-traditional', None, None),
    ('Web', 'curl', 'curl', None, None),
    ('Web', 'wget', 'wget', None, None),
    ('Web', 'git', 'git', None, None),
    ('Web', 'jq', 'jq', None, None),
    ('Web', 'openssl', 'openssl', None, None),
    ('Web', 'masscan', 'masscan', None, None),
    ('Web', 'dnsenum', 'dnsenum', None, None),
    ('Web', 'dnsrecon', 'dnsrecon', None, None),
    ('Web', 'dirsearch', None, 'dirsearch', 'dirsearch'),
    ('Web', 'theHarvester', None, 'theHarvester', None),
    ('Web', 'wafw00f', None, 'wafw00f', None),
    ('Web', 'sslyze', None, 'sslyze', None),
    ('Web', 'xsstrike', None, 'xsstrike', None),
    ('Web', 'arjun', None, 'arjun', None),

    # Forensics
    ('Forensics', 'binwalk', 'binwalk', None, None),
    ('Forensics', 'exiftool', 'exiftool', None, None),
    ('Forensics', 'steghide', 'steghide', None, None),
    ('Forensics', 'zsteg', None, 'gem:zsteg', None),
    ('Forensics', 'tshark', 'tshark', None, None),
    ('Forensics', 'foremost', 'foremost', None, None),
    ('Forensics', 'hashcat', 'hashcat', None, None),
    ('Forensics', 'john', 'john', None, None),
    ('Forensics', 'xxd', 'xxd', None, None),
    ('Forensics', 'pngcheck', 'pngcheck', None, None),
    ('Forensics', 'audacity', 'audacity', None, None),
    ('Forensics', 'sleuthkit', 'sleuthkit', None, None),
    ('Forensics', 'testdisk', 'testdisk', None, None),
    ('Forensics', 'scalpel', 'scalpel', None, None),
    ('Forensics', 'bulk_extractor', 'bulk-extractor', None, None),
    ('Forensics', 'pdftotext', 'poppler-utils', None, None),
    ('Forensics', 'stegoveritas', None, 'stegoveritas', None),
    ('Forensics', 'oletools', 'oletools', 'oletools', 'oletools'),
    ('Forensics', 'pdf-parser', None, 'pdf-parser', None),

    # Pwn
    ('Pwn', 'gdb', 'gdb', None, None),
    ('Pwn', 'strings', 'binutils', None, None),
    ('Pwn', 'objdump', 'binutils', None, None),
    ('Pwn', 'strace', 'strace', None, None),
    ('Pwn', 'ltrace', 'ltrace', None, None),
    ('Pwn', 'patchelf', 'patchelf', None, None),
    ('Pwn', 'ROPgadget', None, 'ROPgadget', None),
    ('Pwn', 'checksec', None, 'checksec.py', None),
    ('Pwn', 'pwntools', None, 'pwntools', 'pwn'),
    ('Pwn', 'angr', None, 'angr', 'angr'),
    ('Pwn', 'z3', None, 'z3-solver', 'z3'),
    ('Pwn', 'keystone', None, 'keystone-engine', 'keystone'),
    ('Pwn', 'unicorn', None, 'unicorn', 'unicorn'),
    ('Pwn', 'qemu-x86_64', 'qemu-user', None, None),

    # RE
    ('RE', 'r2', 'radare2', None, None),
    ('RE', 'unzip', 'unzip', None, None),
    ('RE', 'file', 'file', None, None),
    ('RE', 'upx', 'upx-ucl', None, None),
    ('RE', 'readelf', 'binutils', None, None),
    ('RE', 'nm', 'binutils', None, None),
    ('RE', 'pyelftools', None, 'pyelftools', 'elftools'),
    ('RE', 'lief', None, 'lief', 'lief'),
    ('RE', 'capstone', None, 'capstone', 'capstone'),
    ('RE', 'frida', None, 'frida-tools', 'frida'),

    # Crypto
    ('Crypto', 'openssl', 'openssl', None, None),
    ('Crypto', 'yara', 'yara', None, None),
    ('Crypto', 'hashid', 'hashid', None, None),
    ('Crypto', 'gmpy2', None, 'gmpy2', 'gmpy2'),
    ('Crypto', 'pycryptodome', None, 'pycryptodome', 'Crypto'),
    ('Crypto', 'sage', 'sagemath', None, None),

    # OSINT
    ('OSINT', 'whois', 'whois', None, None),
    ('OSINT', 'dig', 'dnsutils', None, None),
    ('OSINT', 'nslookup', 'dnsutils', None, None),
    ('OSINT', 'traceroute', 'inetutils-traceroute', None, None),
    ('OSINT', 'sherlock', None, 'sherlock-project', 'sherlock'),
    ('OSINT', 'holehe', None, 'holehe', None),
    ('OSINT', 'theHarvester', None, 'theHarvester', None),
    ('OSINT', 'shodan', None, 'shodan', 'shodan'),
    ('OSINT', 'recon-ng', None, 'recon-ng', None),

    # Misc
    ('Misc', 'screen', 'screen', None, None),
    ('Misc', 'tmux', 'tmux', None, None),
    ('Misc', 'htop', 'htop', None, None),
    ('Misc', 'tree', 'tree', None, None),
    ('Misc', 'vim', 'vim', None, None),
    ('Misc', 'nano', 'nano', None, None),
    ('Misc', '7z', 'p7zip-full', None, None),
    ('Misc', 'rsync', 'rsync', None, None),
    ('Misc', 'locate', 'plocate', None, None),
    ('Misc', 'docker', 'docker.io', None, None),
]

# ─── Logging ───────────────────────────────────────────────

def p_header(title):
    print(f'\n{C.BOLD}{C.BLUE}╔══ {C.WHITE}{title}{C.NC}')

def p_section(domain, title):
    c = DOMAIN_COLORS.get(domain, C.CYAN)
    print(f'\n{c}┌─── [{domain}] {title}{C.NC}')

def p_tool(domain, name, ok, detail=''):
    c = DOMAIN_COLORS.get(domain, C.CYAN)
    icon = f'{C.CHECK} {C.GREEN}' if ok else f'{C.CROSS} {C.RED}'
    print(f'  {c}▸{C.NC} {C.BOLD}{name:<24}{C.NC} {icon}{detail:<50}{C.NC}')

def p_info(msg):   print(f'  {C.DIM}•{C.NC} {C.DIM}{msg}{C.NC}')
def p_ok(msg):     print(f'  {C.CHECK} {C.GREEN}{msg}{C.NC}')
def p_warn(msg):   print(f'  {C.YELLOW}⚠ {msg}{C.NC}')
def p_error(msg):  print(f'  {C.CROSS} {C.RED}{msg}{C.NC}')


# ─── Helpers ───────────────────────────────────────────────

def get_env_value(content: str, name: str) -> str:
    prefix = f"{name}="

    for line in content.splitlines():
        if line.startswith(prefix):
            return line.split("=", 1)[1].strip()

    return ""


def set_env_value(content: str, name: str, value: str) -> str:
    prefix = f"{name}="
    lines = content.splitlines()
    updated = False
    result = []

    for line in lines:
        if line.startswith(prefix):
            result.append(f"{name}={value}")
            updated = True
        else:
            result.append(line)

    if not updated:
        result.append(f"{name}={value}")

    return "\n".join(result).strip() + "\n"


def read_key_pool(provider_name: str) -> list[str]:
    while True:
        raw_count = input(
            f"  Number of {provider_name} API keys (0 to skip): "
        ).strip()

        try:
            count = int(raw_count)
            if count >= 0:
                break
        except ValueError:
            pass

        p_warn("Enter a non-negative number")

    keys = []

    for index in range(count):
        while True:
            key = input(
                f"  {provider_name} API key {index + 1}/{count}: "
            ).strip()

            if key:
                keys.append(key)
                break

            p_warn("API key cannot be empty")

    return keys


def configure_llm_keys(content: str) -> str:
    google_keys = get_env_value(content, "GOOGLE_API_KEYS")
    if not google_keys:
        legacy_keys = [
            get_env_value(content, "GEMMA_API_KEYS"),
            get_env_value(content, "GEMINI_API_KEYS"),
        ]
        google_keys = ",".join(key for key in legacy_keys if key)
        if google_keys:
            content = set_env_value(
                content,
                "GOOGLE_API_KEYS",
                google_keys,
            )

    nim_keys = get_env_value(content, "NVIDIA_NIM_API_KEYS")
    if not nim_keys:
        legacy_nim_key = get_env_value(content, "NVIDIA_NIM_API_KEY")
        if legacy_nim_key and legacy_nim_key != "your_key_here":
            nim_keys = legacy_nim_key
            content = set_env_value(
                content,
                "NVIDIA_NIM_API_KEYS",
                nim_keys,
            )

    if (
        get_env_value(content, "LLM_KEYS_CONFIGURED") != "1"
        or not (nim_keys or google_keys)
    ):
        nim_keys = read_key_pool("NVIDIA NIM")
        google_keys = read_key_pool("Google AI (Gemma and Gemini)")

        content = set_env_value(
            content,
            "NVIDIA_NIM_API_KEYS",
            ",".join(nim_keys),
        )
        content = set_env_value(
            content,
            "GOOGLE_API_KEYS",
            ",".join(google_keys),
        )
        content = set_env_value(
            content,
            "LLM_KEYS_CONFIGURED",
            "1",
        )

    available = ["nim","gemma","gemini"]

    if not available:
        raise RuntimeError("At least one LLM API key is required")

    print("\n  LLM providers:")
    for index, provider in enumerate(available, start=1):
        print(f"  {index}. {provider.upper()}")

    while True:
        selection = input("  Choose LLM provider: ").strip()

        try:
            provider = available[int(selection) - 1]
            break
        except (ValueError, IndexError):
            p_warn("Choose one of the displayed numbers")

    if not get_env_value(content, "NVIDIA_NIM_API_KEYS") and provider == "nim":
        nim_keys = read_key_pool("NVIDIA NIM")
        content = set_env_value(
            content,
            "NVIDIA_NIM_API_KEYS",
            ",".join(nim_keys),
        )
    elif not get_env_value(content, "GOOGLE_API_KEYS") and (provider == "gemma" or provider == "gemini"):
        google_keys = read_key_pool("Google AI (Gemma and Gemini)")
        content = set_env_value(
            content,
            "GOOGLE_API_KEYS",
            ",".join(google_keys),
        )
    content = set_env_value(content, "LLM_PROVIDER", provider)
    return content

def run_cmd(cmd, capture=False, check=False, timeout=120):
    try:
        result = subprocess.run(
            cmd, capture_output=capture, text=True, timeout=timeout
        )
        if check and result.returncode != 0:
            return None
        return result
    except Exception:
        return None

def check_tool(binary, apt_pkg=None):
    if shutil.which(binary):
        return True
    if apt_pkg:
        r = run_cmd(['dpkg', '-s', apt_pkg], capture=True)
        if r and r.returncode == 0:
            return True
    return False

def tool_version(binary):
    r = run_cmd([binary, '--version'], capture=True, timeout=5)
    if r and r.returncode == 0:
        return r.stdout.strip()[:50] or r.stderr.strip()[:50]
    return ''

def check_python():
    v = sys.version_info
    if v.major < 3 or (v.major == 3 and v.minor < 8):
        p_error(f'Python 3.8+ required, got {v.major}.{v.minor}')
        sys.exit(1)
    p_ok(f'Python {v.major}.{v.minor}.{v.micro}')


# ─── Virtual Environment ───────────────────────────────────

def ensure_venv():
    p_header('PYTHON VIRTUAL ENVIRONMENT')
    if not VENV_DIR.exists():
        p_info('Creating virtual environment...')
        r = run_cmd([sys.executable, '-m', 'venv', str(VENV_DIR)], timeout=60)
        if r is None or r.returncode != 0:
            p_error('Failed to create venv')
            sys.exit(1)
        p_ok('Virtual environment created')
    else:
        p_ok('Virtual environment exists')

    # Get the venv python to re-exec with
    venv_python = VENV_DIR / 'bin' / 'python3'
    if not venv_python.exists():
        venv_python = VENV_DIR / 'bin' / 'python'
    if not venv_python.exists():
        p_error('Cannot find venv python')
        sys.exit(1)

    # If we're not already running inside the venv, re-exec
    if sys.prefix != str(VENV_DIR):
        p_info('Re-launching inside virtual environment...')
        os.execl(str(venv_python), str(venv_python), *sys.argv)

    # Upgrade pip
    p_info('Upgrading pip...')
    run_cmd([str(venv_python), '-m', 'pip', 'install', '--quiet', '--upgrade', 'pip'], timeout=60)
    p_ok('pip upgraded')
    return str(venv_python)


# ─── Python Dependencies ───────────────────────────────────

def install_python_deps(python_exe):
    p_header('PYTHON DEPENDENCIES')

    if REQUIREMENTS.exists():
        requirements = []

        with open(REQUIREMENTS) as f:
            for line in f:
                line = line.strip()

                if not line or line.startswith("#"):
                    continue

                requirements.append(line)

        total = len(requirements)

        p_info(f"Installing {total} Python packages...")
        packages = [
            p for p in requirements
            if not p.startswith("gem:")
        ]
        for i, package in enumerate(packages, 1):
            p_info(f"[{i}/{total}] {package}")

            r = run_cmd(
                [
                    python_exe,
                    "-m",
                    "pip",
                    "install",
                    package,
                ],capture=True,
                timeout=180,
            )

            output = (r.stdout or "") + (r.stderr or "")

            if r.returncode == 0:
                if "Requirement already satisfied" in output:
                    p_ok("Already installed")
                else:
                    p_ok("Installed")
            else:
                p_error("Failed")

                # showing a concise reason
                for line in reversed(output.splitlines()):
                    if line.strip():
                        print(f"    {line}")
                        break

    # Install domain-specific pip packages
    pip_packages = set()
    for _, _, _, pip_pkg, _ in TOOLS:
        if pip_pkg:
            pip_packages.add(pip_pkg)

    extra_pkgs = {
        "requests",
        "beautifulsoup4",
        "pillow",
        "matplotlib",
        "jupyter",
        "ipython",
        "prompt-toolkit",
    }
    pip_packages.update(extra_pkgs)

    packages = sorted(pip_packages)
    packages = [
        p for p in packages
        if not p.startswith("gem:")
    ]
    installed = 0
    already_installed = 0
    failed = []

    p_info(f"Installing {len(packages)} CTF Python packages...")

    for i, pkg in enumerate(packages, 1):
        p_info(f"[{i}/{len(packages)}] Installing {pkg}...")

        r = run_cmd(
            [python_exe, "-m", "pip", "install", pkg],capture=True,
            timeout=120,
        )

        output = (r.stdout or "") + (r.stderr or "")

        if r.returncode == 0:
            if (
                    "Requirement already satisfied" in output
                    or "Already satisfied" in output
            ):
                p_info("  ✓ Already installed")
                already_installed += 1
            else:
                p_info("  ✓ Installed")
                installed += 1
        else:
            p_error("  ✗ Failed")
            failed.append(pkg)

            for line in reversed(output.splitlines()):
                line = line.strip()
                if line:
                    p_error(f"    {line}")
                    break

            # Print the last meaningful error line
            for line in reversed(output.splitlines()):
                line = line.strip()
                if line:
                    p_error(f"    {line}")
                    break

    print()
    p_info("Python package installation summary")
    p_info(f"  ✓ Installed: {installed}")
    p_info(f"  ✓ Already installed: {already_installed}")

    if failed:
        p_error(f"  ✗ Failed: {len(failed)}")
        for pkg in failed:
            p_error(f"    • {pkg}")
    else:
        p_info("  ✓ All packages installed successfully.")


# ─── System Tools ──────────────────────────────────────────

def _sudo(cmd):
    """Prefix command list with sudo if not root and sudo is available."""
    if os.geteuid() != 0 and shutil.which('sudo'):
        return ['sudo'] + cmd
    return cmd

def _pip_cmd(pkg):
    """Install a pip package using the venv python (or fallback with --break-system-packages).
    Supports gem: prefix for Ruby gem packages."""
    # Gem-based install
    if pkg.startswith('gem:'):
        gem_name = pkg[4:]
        return ['gem', 'install', gem_name]
    # Try venv pip first
    for py in [VENV_DIR / 'bin' / 'python3', VENV_DIR / 'bin' / 'python']:
        if py.exists():
            return [str(py), '-m', 'pip', 'install', '--quiet', pkg]
    # Fallback: system python with override
    return [sys.executable, '-m', 'pip', 'install', '--quiet', '--break-system-packages', pkg]

def install_system_tools():
    p_header('DOMAIN TOOLKIT INSTALLATION')

    has_sudo = shutil.which('sudo') and os.geteuid() != 0
    is_root = os.geteuid() == 0

    if is_root:
        p_ok('Running as root')
    elif has_sudo:
        p_warn('Not running as root — using sudo')
    else:
        p_warn('Not root and no sudo — skipping system package installs')

    # Fix any interrupted dpkg state first
    if is_root or has_sudo:
        run_cmd(_sudo(['dpkg', '--configure', '-a']), timeout=60)

    # Update apt
    if is_root or has_sudo:
        p_info('Running apt-get update...')
        run_cmd(_sudo(['apt-get', 'update', '-qq']), timeout=120)
        p_ok('Package list updated')

    # Install by domain
    domains = ['Web', 'Forensics', 'Pwn', 'RE', 'Crypto', 'OSINT', 'Misc']
    for domain in domains:
        domain_tools = [(b, a, p) for d, b, a, p, _ in TOOLS if d == domain]
        missing = [(b, a, p) for b, a, p in domain_tools if not check_tool(b, a)]

        p_section(domain, f'{len(domain_tools)} tools, {len(missing)} to install')

        installed_count = 0
        for binary, apt_pkg, pip_pkg in domain_tools:
            if check_tool(binary, apt_pkg):
                ver = tool_version(binary)
                p_tool(domain, binary, True, ver)
                installed_count += 1
                continue

            if not (is_root or has_sudo):
                p_tool(domain, binary, False, 'no root')
                continue

            # Install pip package if applicable (use venv pip, not system)
            pip_ok = False
            if pip_pkg:
                r = run_cmd(_pip_cmd(pip_pkg), timeout=120, capture=True)
                pip_ok = r and r.returncode == 0

            # Install apt package (skip if no apt package name AND pip succeeded for a check-only binary)
            install_pkg = apt_pkg or (binary if not pip_pkg else None)
            if install_pkg:
                env = os.environ.copy()
                env['DEBIAN_FRONTEND'] = 'noninteractive'
                env['NEEDRESTART_MODE'] = 'a'
                subprocess.run(
                    _sudo(['apt-get', 'install', '-y', install_pkg]),
                    timeout=120, env=env,
                    capture_output=True,
                )

            # Verify: check binary/apt first, then fall back to import check
            found = check_tool(binary, apt_pkg)
            if not found and pip_pkg:
                # Try import-based verification
                for import_name in [pip_pkg.replace('-', '_'), pip_pkg.replace('-', '')]:
                    r = run_cmd(
                        [sys.executable, '-c', f'import {import_name}'],
                        capture=True, timeout=5,
                    )
                    if r and r.returncode == 0:
                        found = True
                        break

            if found:
                ver = tool_version(binary)
                p_tool(domain, binary, True, ver)
                installed_count += 1
            elif pip_ok:
                p_tool(domain, binary, True, 'pip OK (no binary)')
                installed_count += 1
            else:
                p_tool(domain, binary, False, 'install FAILED')

        # Show progress bar
        total = len(domain_tools)
        pct = installed_count * 100 // total if total else 0
        bar_len = 20
        filled = pct * bar_len // 100
        bar = '█' * filled + '░' * (bar_len - filled)
        c = DOMAIN_COLORS.get(domain, C.CYAN)
        print(f'  {c}└─{C.NC} [{C.GREEN}{bar}{C.NC}] {pct}% ({installed_count}/{total})')


# ─── Environment Setup ─────────────────────────────────────

def setup_environment():
    p_header('ENVIRONMENT CONFIGURATION')

    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not ENV_FILE.exists():
        if ENV_EXAMPLE.exists():
            shutil.copy(ENV_EXAMPLE, ENV_FILE)
        else:
            ENV_FILE.write_text(
                'NVIDIA_NIM_API_KEY=your_key_here\n'
                'NVIDIA_NIM_BASE_URL=https://integrate.api.nvidia.com/v1\n'
            )

    content = ENV_FILE.read_text()
    content = configure_llm_keys(content)
    content = set_env_value(content, "GEMMA_MODEL", "gemma-4-31b-it")
    content = set_env_value(
        content,
        "GEMINI_MODEL",
        "gemini-3.1-flash-lite",
    )
    ENV_FILE.write_text(content)
    p_ok(
        f"LLM provider set to "
        f"{get_env_value(content, 'LLM_PROVIDER').upper()}"
    )

    flag_fmt = None
    for line in content.splitlines():
        if line.startswith('FLAG_FORMAT='):
            val = line.split('=', 1)[1].strip()
            if val:
                flag_fmt = val
            break
    if not flag_fmt:
        print(f'\n  {C.DIM}Set the default flag format for your CTF (e.g. [bold]picoCTF{{...}}[/bold], [bold]CTF{{...}}[/bold]){C.NC}')
        print(f'  {C.DIM}Leave empty to skip.{C.NC}')
        fmt = input(f'  {C.CYAN}▸{C.NC} Flag format: ').strip()
        if fmt:
            if 'FLAG_FORMAT=' in content:
                lines = content.splitlines()
                new_lines = []
                for line in lines:
                    if line.startswith('FLAG_FORMAT='):
                        new_lines.append(f'FLAG_FORMAT={fmt}')
                    else:
                        new_lines.append(line)
                content = '\n'.join(new_lines) + '\n'
            else:
                content += f'\nFLAG_FORMAT={fmt}\n'
            ENV_FILE.write_text(content)
            p_ok(f'Flag format set to {fmt}')
        else:
            p_info('No flag format set')

    (BASE_DIR / 'uploads').mkdir(exist_ok=True)
    (BASE_DIR / 'data').mkdir(exist_ok=True)
    p_ok('Directories: uploads/, data/')


# ─── Verification ──────────────────────────────────────────

def verify():
    p_header('VERIFICATION')

    all_tools = len(TOOLS)
    found = 0
    domains = ['Web', 'Forensics', 'Pwn', 'RE', 'Crypto', 'OSINT', 'Misc']

    # Find venv python for import checks
    _check_python = sys.executable
    for _py in [VENV_DIR / 'bin' / 'python3', VENV_DIR / 'bin' / 'python']:
        if _py.exists():
            _check_python = str(_py)
            break

    for domain in domains:
        c = DOMAIN_COLORS.get(domain, C.CYAN)
        domain_tools = [(b, a, p, v) for d, b, a, p, v in TOOLS if d == domain]
        domain_found = 0

        print(f'\n{c}┌─── [{domain}] ({len(domain_tools)} tools){C.NC}')
        for binary, apt_pkg, pip_pkg, verify_import in domain_tools:
            ok = check_tool(binary, apt_pkg)
            # Fall back to import-based verification for pip-only packages
            if not ok and pip_pkg and not pip_pkg.startswith('gem:'):
                import_names = []
                if verify_import:
                    import_names.append(verify_import)
                import_names += [pip_pkg.replace('-', '_'), pip_pkg.replace('-', '')]
                for import_name in import_names:
                    r = run_cmd([_check_python, '-c', f'import {import_name}'], capture=True, timeout=5)
                    if r and r.returncode == 0:
                        ok = True
                        break
            # Also check gem packages
            if not ok and pip_pkg and pip_pkg.startswith('gem:'):
                gem_name = pip_pkg[4:]
                r = run_cmd(['gem', 'list', '-i', gem_name], capture=True, timeout=5)
                if r and r.returncode == 0 and 'true' in r.stdout:
                    ok = True

            if ok:
                domain_found += 1
                found += 1
                ver = tool_version(binary)
                print(f'  {C.CHECK} {C.GREEN}{binary:<24}{C.NC} {C.DIM}{ver}{C.NC}')
            else:
                print(f'  {C.CROSS} {C.RED}{binary:<24}{C.NC} {C.DIM}missing{C.NC}')

        total = len(domain_tools)
        pct = domain_found * 100 // total if total else 0
        bar_len = 20
        filled = pct * bar_len // 100
        bar = '█' * filled + '░' * (bar_len - filled)
        print(f'{c}│{C.NC}\n  {c}└─{C.NC} [{C.GREEN}{bar}{C.NC}] {pct}% ({domain_found}/{total})')

    pct = found * 100 // all_tools if all_tools else 0
    bar_len = 20
    filled = pct * bar_len // 100
    bar = '█' * filled + '░' * (bar_len - filled)
    print()
    p_header(f'OVERALL [{C.GREEN}{bar}{C.NC}] {pct}% ({found}/{all_tools})')

    if found == all_tools:
        p_ok('All tools installed!')
    else:
        p_warn(f'{all_tools - found} tools missing — some features may not work')
    print()


# ─── CLI Launch ────────────────────────────────────────────

def launch_cli():
    # Import and run CLI now that everything is installed
    p_header('LAUNCHING CLI')
    p_ok('Starting CTFAgent interactive console...')
    print()
    from cli.client import main
    main()


# ═══════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════

def check_uptodate():
    """Quick check if we need a full installation."""
    if not VENV_DIR.exists():
        return False
    venv_python = VENV_DIR / 'bin' / 'python3'
    if not venv_python.exists():
        return False
    # Check core deps
    try:
        import rich
        import langgraph
        import httpx
    except ImportError:
        return False
    return True


def run_install_only():
    """Install system tools only (called from CLI 'install' command via sudo)."""
    import shutil
    from pathlib import Path

    # Ensure venv exists so pip installs go to the right place
    if not VENV_DIR.exists() or not (VENV_DIR / 'bin' / 'python3').exists():
        p_info('Virtual environment needed — creating...')
        r = run_cmd([sys.executable, '-m', 'venv', str(VENV_DIR)], timeout=60)
        if r is None or r.returncode != 0:
            p_warn('Could not create venv; pip packages may fail')
    venv_python = VENV_DIR / "bin" / "python3"
    if not venv_python.exists():
        venv_python = VENV_DIR / "bin" / "python"

    install_python_deps(str(venv_python))
    install_system_tools()
    setup_environment()
    # Special: pwndbg
    if not shutil.which('pwndbg') and not (Path('/opt/pwndbg').exists()):
        p_info('Installing pwndbg from GitHub...')
        run_cmd(['git', 'clone', '--depth=1',
                 'https://github.com/pwndbg/pwndbg', '/opt/pwndbg'], timeout=60)
        if (Path('/opt/pwndbg') / 'setup.sh').exists():
            run_cmd(['/opt/pwndbg/setup.sh'], timeout=120)
        if shutil.which('pwndbg'):
            p_ok('pwndbg installed')
        else:
            p_warn('pwndbg setup incomplete (optional)')
    verify()
    print(f'\n  {C.CHECK} {C.GREEN}Installation complete!{C.NC}\n')


def check_root():
    """Warn if not running as root (many tools need it)."""
    if os.geteuid() != 0:
        has_sudo = shutil.which('sudo') is not None
        if has_sudo:
            p_warn('Not running as root — sudo available, but some tools may fail')
        else:
            p_warn('Not running as root and no sudo — many tools will fail to install')

def run_docker_cli():
    """Docker images already include dependencies; run only first-use config."""
    p_header('DOCKER STARTUP')
    check_python()
    p_ok('Using dependencies baked into the Docker image')
    p_info(f'Configuration file: {ENV_FILE}')
    setup_environment()

    from cli.client import main as cli_main
    cli_main()


def run_docker_api():
    """Start the API container after configuration has been created."""
    p_header('DOCKER API STARTUP')
    check_python()
    p_info(f'Configuration file: {ENV_FILE}')
    if not ENV_FILE.exists():
        p_error('Docker API configuration is missing.')
        p_info('Run the interactive Docker CLI first: docker compose run --rm ctfagent')
        sys.exit(1)

    from backend.main import app
    import uvicorn

    uvicorn.run(app, host='0.0.0.0', port=8000)


def main():
    if '--docker' in sys.argv:
        run_docker_cli()
        return

    if '--docker-api' in sys.argv:
        run_docker_api()
        return

    # Handle --install-only mode (called from CLI 'install' command via sudo)
    if '--install-only' in sys.argv:
        check_root()
        run_install_only()
        return

    check_root()
    check_python()

    # If everything looks up-to-date, skip install and go straight to CLI
    if check_uptodate():
        # Re-exec in venv if needed
        venv_python = VENV_DIR / 'bin' / 'python3'
        if sys.prefix != str(VENV_DIR) and venv_python.exists():
            os.execl(str(venv_python), str(venv_python), *sys.argv)

        # Still prompt for API key if missing
        setup_environment()

        from cli.client import main as cli_main
        cli_main()
        return

    # Full installation flow
    python_exe = ensure_venv()

    # ensure_venv re-execs into venv, so after this point we're inside venv
    install_python_deps(python_exe)

    run_install_only()

    print(f'\n  {C.BOLD}{C.GREEN}╔══════════════════════════════════════════════════╗{C.NC}')
    print(f'  {C.BOLD}{C.GREEN}║     🚩 CTFAgent is ready! Happy Hacking! 🚩     ║{C.NC}')
    print(f'  {C.BOLD}{C.GREEN}╚══════════════════════════════════════════════════╝{C.NC}')
    print(f'\n  {C.ARROW} Launching interactive console...\n')

    from cli.client import main as cli_main
    cli_main()


if __name__ == '__main__':
    main()
