# Forensics Knowledge

## File Analysis
### File Type Detection
- `file` command: first magic bytes check
- `xxd` / `hexdump` for raw analysis
- Corrupted headers: `hexedit` to repair magic bytes

### Embedded Files
- `binwalk -Me file.bin`: recursive extraction
- `foremost -i file.bin`: file carving by headers
- `strings file | grep -i "flag\|ctf\|secret"`
- `scalpel`: configurable carving

### Memory Analysis
- **Volatility 3**: `vol -f mem.dump windows.pslist`
  - `windows.cmdline`, `windows.netscan`, `windows.dumpfiles`
  - `windows.malfind` for injected code
  - `windows.memmap`, `windows.handles`
- **LiME**: memory acquisition on Linux

## Network Forensics (PCAP)
### Analysis Tools
- `tshark -r capture.pcap -Y "http.request" -T fields -e http.host -e http.request.uri`
- `tcpflow -r capture.pcap` -> reconstruct TCP streams
- Wireshark: Follow TCP/UDP/HTTP Stream

### Common Artifacts
- `http` endpoints, `dns` queries, `tls` handshakes
- Extract objects: `tshark -r capture.pcap --export-objects http,/output/`
- Kerberos tickets, NTLM hashes from SMB traffic
- USB HID data: keyboard/mouse captures

### Wireless
- Aircrack-ng suite, WPA handshake capture
- SSID beacon analysis, deauth detection

## Steganography
### Image Steganography
- **LSB**: `zsteg -a image.png` (PNG/BMP)
- **steghide**: `steghide extract -sf image.jpg` (JPEG)
- **stegsolve**: LSB/bit plane analysis
- **ImageMagick**: `compare`, color channel manipulation
- Check appended data after IEND (PNG) or FFD9 (JPEG)

### Audio Steganography
- **Spectrogram**: check with Audacity, Sonic Visualiser
- **DTMF decoding**: check spectrogram for dual-tone patterns
- **WAV Stego**: LSB in audio samples
- **MP3Stego**: decode hidden data

### Other Formats
- PDF: check for embedded files, hidden text (white-on-white)
- Office documents: OLE objects, macros (olevba, oledump)
- Video: frames contain steganographic data

## Disk Images
- `mmls image.dd`: partition table
- `fls -o OFFSET image.dd`: file listing
- `icat -o OFFSET image.dd INODE > output`: extract specific file
- Mount: `mount -o loop,ro,offset=$((512 * OFFSET)) image.dd /mnt`
- Recovering deleted files: `extundelete`, `testdisk`, `photorec`

## Registry Forensics (Windows)
- SAM / SYSTEM: extract password hashes
- NTUSER.DAT: user activity, MRU, typed URLs
- AmCache.hve: recently executed programs
- UserAssist: GUI program execution count/timestamps
- Tool: `regripper`, `python-registry`

## Log Analysis
- Syslog, auth.log (Linux): failed logins, sudo usage
- Windows Event Log: Security (4624 logon, 4625 failed), System
- Apache/Nginx access logs: SQLi attempts, path traversal
- Docker logs: `docker logs container_id`

## Firmware
- `binwalk -Me firmware.bin` -> filesystem extraction
- Check for squashfs, ubifs, cramfs
- Unsquashfs, jefferson (JFFS2)
- Common credentials in /etc/shadow, web interfaces

## Smart Card / NFC
- `mfoc` for MIFARE classic key recovery
- `proxmark3` for raw NFC communication
- APDU tracing, sector key cracking

## Cryptocurrency / Blockchain
- Address clustering, taint analysis
- Bitcoin: blockchain.info, blockchair
- Ethereum: etherscan.io
- Transaction graph analysis

## File Carving with Scalpel
- Edit `/etc/scalpel/scalpel.conf` to enable file types
- `scalpel -o output_dir image.dd`
- Carves by header/footer signatures (magic bytes)
