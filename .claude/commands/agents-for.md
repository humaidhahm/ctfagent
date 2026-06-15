---
description: List CTFAgent capabilities relevant to a domain or tag (web, pwn, crypto, forensics, etc.).
argument-hint: <domain or tag>
---

Filter the CTFAgent capability catalog by the domain or tag below.

Filter:
$ARGUMENTS

Match against this taxonomy:

```
web / http     → sqlmap, ffuf, gobuster, curl_probe, whatweb, nikto
pwn / binary   → pwntools, checksec, ROPgadget, gdb, angr
re / reverse   → radare2, strings, objdump, ghidra
crypto         → cipher_cracker, rsa_solver, encoding_detector, openssl
forensics      → binwalk, exiftool, steghide, zsteg, tshark, foremost
osint          → whois, dig, sherlock, holehe, shodan, theHarvester
misc           → download_file, file_reader, binary_calc
stego          → zsteg, steghide, stegseek, binwalk, pngcheck
```
