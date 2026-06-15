#!/usr/bin/env bash
# CTFAgent tool installation audit
# Reports which tools are present on this system, grouped by domain

set -uo pipefail

GREEN=$'\033[0;32m'
RED=$'\033[0;31m'
YELLOW=$'\033[0;33m'
DIM=$'\033[0;90m'
BOLD=$'\033[1m'
NC=$'\033[0m'
OK="✔"
MISS="✘"
OPT="○"

TOOLS=(
    # Web
    "sqlmap|Web|required|apt install sqlmap | pipx install sqlmap"
    "gobuster|Web|required|apt install gobuster"
    "ffuf|Web|required|apt install ffuf | go install github.com/ffuf/ffuf/v2@latest"
    "nikto|Web|optional|apt install nikto"
    "whatweb|Web|optional|apt install whatweb"
    "wfuzz|Web|optional|apt install wfuzz"
    "nmap|Web|required|apt install nmap"
    "nc|Web|required|apt install netcat-traditional"
    "curl|Web|required|apt install curl"
    "masscan|Web|optional|apt install masscan"
    "dnsenum|Web|optional|apt install dnsenum"

    # Forensics
    "binwalk|Forensics|required|apt install binwalk"
    "exiftool|Forensics|required|apt install exiftool"
    "steghide|Forensics|required|apt install steghide"
    "zsteg|Forensics|required|gem install zsteg"
    "tshark|Forensics|required|apt install tshark"
    "foremost|Forensics|required|apt install foremost"
    "hashcat|Forensics|optional|apt install hashcat"
    "john|Forensics|optional|apt install john"
    "pngcheck|Forensics|optional|apt install pngcheck"
    "sleuthkit|Forensics|optional|apt install sleuthkit"
    "testdisk|Forensics|optional|apt install testdisk"
    "scalpel|Forensics|optional|apt install scalpel"
    "bulk_extractor|Forensics|optional|apt install bulk-extractor"
    "stegoveritas|Forensics|optional|pipx install stegoveritas"
    "oletools|Forensics|optional|pipx install oletools"

    # Pwn
    "gdb|Pwn|required|apt install gdb"
    "strings|Pwn|required|apt install binutils"
    "objdump|Pwn|required|apt install binutils"
    "strace|Pwn|optional|apt install strace"
    "patchelf|Pwn|optional|apt install patchelf"
    "ROPgadget|Pwn|required|pipx install ROPgadget"
    "checksec|Pwn|required|pipx install checksec.py"
    "pwntools|Pwn|required|pipx install pwntools"
    "angr|Pwn|optional|pipx install angr"
    "qemu-x86_64|Pwn|optional|apt install qemu-user"

    # RE
    "r2|RE|required|apt install radare2"
    "unzip|RE|required|apt install unzip"
    "file|RE|required|apt install file"
    "upx|RE|optional|apt install upx-ucl"
    "readelf|RE|required|apt install binutils"
    "frida|RE|optional|pipx install frida-tools"

    # Crypto
    "openssl|Crypto|required|apt install openssl"
    "yara|Crypto|optional|apt install yara"
    "hashid|Crypto|optional|apt install hashid"

    # OSINT
    "whois|OSINT|required|apt install whois"
    "dig|OSINT|required|apt install dnsutils"
    "nslookup|OSINT|required|apt install dnsutils"
    "traceroute|OSINT|optional|apt install inetutils-traceroute"
    "sherlock|OSINT|optional|pipx install sherlock-project"
    "holehe|OSINT|optional|pipx install holehe"
    "shodan|OSINT|optional|pipx install shodan"

    # Misc
    "screen|Misc|optional|apt install screen"
    "tmux|Misc|optional|apt install tmux"
    "htop|Misc|optional|apt install htop"
    "tree|Misc|optional|apt install tree"
    "7z|Misc|optional|apt install p7zip-full"
    "docker|Misc|optional|apt install docker.io"
)

ONLY_DOMAIN=""
JSON_OUTPUT=0
QUIET=0

usage() {
    cat <<EOF
Usage: doctor.sh [options]

Audit which CTF tools are installed on your system.

Options:
  --domain <name>   Filter to a specific domain (Web, Forensics, Pwn, RE, Crypto, OSINT, Misc)
  --json            Emit JSON output
  --quiet           Only show missing required tools
  -h, --help        Show this help

Exit codes:
  0  All required tools present
  1  At least one required tool missing
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --domain) ONLY_DOMAIN="$2"; shift 2 ;;
        --json) JSON_OUTPUT=1; shift ;;
        --quiet) QUIET=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
    esac
done

declare -A DOMAIN_TOTAL=()
declare -A DOMAIN_PRESENT=()
declare -A DOMAIN_REQ_MISSING=()
RESULTS=()
REQ_MISSING_COUNT=0

for entry in "${TOOLS[@]}"; do
    IFS='|' read -r bin domain category hint <<< "$entry"

    if [[ -n "$ONLY_DOMAIN" ]] && [[ "$domain" != "$ONLY_DOMAIN" ]]; then
        continue
    fi

    if command -v "$bin" >/dev/null 2>&1; then
        status="present"
    else
        status="missing"
    fi

    DOMAIN_TOTAL[$domain]=$((${DOMAIN_TOTAL[$domain]:-0} + 1))
    if [[ "$status" == "present" ]]; then
        DOMAIN_PRESENT[$domain]=$((${DOMAIN_PRESENT[$domain]:-0} + 1))
    elif [[ "$category" == "required" ]]; then
        DOMAIN_REQ_MISSING[$domain]=$((${DOMAIN_REQ_MISSING[$domain]:-0} + 1))
        REQ_MISSING_COUNT=$((REQ_MISSING_COUNT + 1))
    fi

    RESULTS+=("$bin|$domain|$category|$status|$hint")
done

if [[ "$JSON_OUTPUT" == "1" ]]; then
    printf '{\n  "tools": [\n'
    first=1
    for r in "${RESULTS[@]}"; do
        IFS='|' read -r bin domain category status hint <<< "$r"
        [[ $first -eq 1 ]] || printf ',\n'
        first=0
        printf '    {"binary":"%s","domain":"%s","category":"%s","status":"%s"}' \
            "$bin" "$domain" "$category" "$status"
    done
    printf '\n  ],\n  "required_missing": %d\n}\n' "$REQ_MISSING_COUNT"
    [[ $REQ_MISSING_COUNT -gt 0 ]] && exit 1 || exit 0
fi

echo "${BOLD}CTFAgent tool audit${NC}"
echo "${DIM}$(date '+%Y-%m-%d %H:%M:%S')  host: $(hostname)${NC}"
echo

declare -A BY_DOMAIN=()
for r in "${RESULTS[@]}"; do
    IFS='|' read -r bin domain category status hint <<< "$r"
    BY_DOMAIN[$domain]="${BY_DOMAIN[$domain]:-}$r"$'\n'
done

DOMAIN_ORDER=("Web" "Forensics" "Pwn" "RE" "Crypto" "OSINT" "Misc")

for domain in "${DOMAIN_ORDER[@]}"; do
    [[ -z "${BY_DOMAIN[$domain]:-}" ]] && continue

    total="${DOMAIN_TOTAL[$domain]:-0}"
    present="${DOMAIN_PRESENT[$domain]:-0}"
    req_miss="${DOMAIN_REQ_MISSING[$domain]:-0}"

    if [[ "$QUIET" == "1" ]] && [[ "$req_miss" == "0" ]]; then
        continue
    fi

    if [[ "$req_miss" -gt 0 ]]; then
        header_color="$RED"
    elif [[ "$present" -lt "$total" ]]; then
        header_color="$YELLOW"
    else
        header_color="$GREEN"
    fi

    printf "${BOLD}${header_color}%s${NC}  ${DIM}(%d/%d present)${NC}\n" \
        "$domain" "$present" "$total"

    while IFS= read -r r; do
        [[ -z "$r" ]] && continue
        IFS='|' read -r bin domain category status hint <<< "$r"

        if [[ "$status" == "present" ]]; then
            [[ "$QUIET" == "1" ]] && continue
            printf "  ${GREEN}%s${NC} %-22s ${DIM}%s${NC}\n" "$OK" "$bin" "$category"
        else
            sym="$MISS"
            col="$RED"
            [[ "$category" != "required" ]] && sym="$OPT" && col="$YELLOW"
            printf "  ${col}%s${NC} %-22s ${DIM}%s${NC}\n" "$sym" "$bin" "$category"
            printf "      ${DIM}↳ %s${NC}\n" "$hint"
        fi
    done <<< "${BY_DOMAIN[$domain]}"
    echo
done

total_tools=${#TOOLS[@]}
present_total=0
for k in "${!DOMAIN_PRESENT[@]}"; do
    present_total=$((present_total + ${DOMAIN_PRESENT[$k]}))
done

printf "${BOLD}Summary${NC}\n"
printf "  ${GREEN}%s${NC} %d / %d tools detected\n" "$OK" "$present_total" "$total_tools"
if [[ "$REQ_MISSING_COUNT" -gt 0 ]]; then
    printf "  ${RED}%s${NC} %d required tool%s missing\n" \
        "$MISS" "$REQ_MISSING_COUNT" "$([ "$REQ_MISSING_COUNT" -eq 1 ] && echo "" || echo "s")"
    exit 1
else
    printf "  ${GREEN}%s${NC} All required tools present\n" "$OK"
    exit 0
fi
