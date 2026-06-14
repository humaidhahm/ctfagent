# Reverse Engineering Knowledge

## Static Analysis
- `r2 -A ./binary`: analyze all, `afl` list functions, `pdf @main` disassemble
- `strings ./binary | grep -i flag`: quick flag pattern search
- `objdump -d ./binary | less`: disassembly dump
- `readelf -a ./binary`: ELF headers, sections, symbols

## Dynamic Analysis
- `strace -f ./binary`: syscall trace
- `ltrace ./binary`: library call trace
- `gdb ./binary`: `b *main+42`, `r`, `x/s $rdi`, `info registers`
- `perf trace ./binary`: performance + syscall tracing

## Anti-Debug Detection
- `ptrace(PTRACE_TRACEME, ...)` -> detect debugger: patch `je` to `jne` or nop
- `/proc/self/status` TracerPid check: patch or LD_PRELOAD
- Timing checks: `rdtsc` difference; patch or skip
- `getenv("LD_PRELOAD")` -> unset or provide fake

## Obfuscation Techniques
- **XOR obfuscation**: single-byte key brute-force, look for repeating patterns
- **Base64 encoding**: search for base64 alphabet in binary
- **Control flow flattening**: restore CFG by tracking dispatcher variable
- **Opaque predicates**: always-true/false conditions, simplify via symbolic execution
- **Virtualization**: custom VM bytecode, extract opcode mapping, build emulator

## Packers / Protectors
- **UPX**: `upx -d ./packed` (standard unpacking)
- **ASPack / FSG**: use generic unpacker or manual unpack (OEP finding)
- **VMProtect / Themida**: advanced protection, look for virtualized code sections
- Detect with: `Detect It Easy (die)` or `file` command

## Firmware Analysis
- `binwalk -Me firmware.bin`: extract filesystems
- Check for: squashfs, jffs2, cramfs, ubi images
- `unsquashfs` for squashfs extraction
- Look for: web interfaces, hardcoded credentials, backdoors

## Android Reverse Engineering
- `apktool d app.apk` -> decode resources
- `jadx-gui app.apk` -> Java decompilation
- `dex2jar` -> convert to JAR, then JD-GUI
- Native libs in `lib/` -> ARM/ARM64 reverse with r2/Ghidra

## WebAssembly (WASM)
- `wasm-decompile file.wasm` -> pseudo-code
- `wasm2wat file.wasm` -> WAT text format
- Browser dev tools for dynamic analysis

## Common Patterns
- **RC4**: look for 256-byte S-box initialization, swapping loop
- **CRC / checksum**: 32-bit polynomial division, often at end of function
- **Base64**: 64-char alphabet string, `!=` padding
- **Encryption constants**: AES S-box (256 bytes), DES IP table
