# OSINT Knowledge

## Search Techniques
### Google Dorking
- `site:target.com filetype:pdf`
- `inurl:admin`, `intitle:"index of"`
- `cache:target.com` -> cached version
- `link:target.com` -> backlinks

### Shodan
- Search for exposed services: `port:22 country:US`
- Banner analysis for version info
- `ssl.cert.issuer.cn:target.com`

## DNS Reconnaissance
### Record Types
- `A`, `AAAA`, `CNAME`, `MX`, `NS`, `TXT` (SPF, DKIM), `SOA`
- `dig any example.com`
- `nslookup -type=any example.com`

### Subdomain Enumeration
- `dnsrecon -d example.com`
- `sublist3r -d example.com`
- `amass enum -d example.com`
- Bruteforce with `dnsenum` or custom wordlist

### Zone Transfer
- `dig axfr @ns1.example.com example.com`
- Rare but extremely revealing

## Social Media
### Username Search
- `whatsmyname.app` or `sherlock` tool
- `maigret` for advanced social search

### Metadata Analysis
- EXIF from photos: GPS coordinates, camera model, timestamp
- Document metadata: author, organization, creation software
- Tool: `exiftool`, `mat2`

## Email OSINT
### SPF/DMARC Records
- `dig TXT _dmarc.example.com`
- SPF: authorized mail servers, may leak internal IPs

### Email Verification
- `smtp_enum` or `smtp-user-enum` for SMTP VRFY/EXPN
- `holehe` to check account existence on services

## Geolocation
- Reverse image search (Google Images, TinEye)
- EXIF GPS data
- Landmark identification
- Timezone/map analysis
- Cellular tower data

## Wayback Machine
- `web.archive.org` -> historical snapshots
- Discover hidden endpoints, old versions
- `waybackpy` Python library
- `waybackurls` tool for URL extraction

## Certificate Transparency
- `crt.sh` -> query: `%.example.com`
- Discover subdomains from SSL certificates
- Historical certificate data

## WHOIS
- Domain registration info
- `whois example.com`
- May reveal: registrar, creation/expiry, nameservers
- Privacy protection may obscure real owner

## Data Breaches
- Have I Been Pwned (HIBP) API
- Dehashed, IntelX, leaked credential databases
- Check compromised passwords, email addresses

## Dark Web
- Tor hidden services: `.onion` domains
- Ahmia search engine
- Recon on dark web forums / marketplaces

## Image OSINT
### Reverse Image Search
- Google Images, TinEye, Yandex Images
- Find original source, location, related images

### Content Analysis
- Text extraction via OCR (tesseract)
- Face detection, object detection
- PhotoDNA / hashing for duplicates

## IP / Network OSINT
- `whois <IP>` -> ASN, organization, geolocation
- AbuseIPDB, VirusTotal
- Reverse DNS, passive DNS (PDNS)
- RIPE / ARIN / APNIC database lookups

## Tool Collection
- `theHarvester`: email, subdomain, IP enumeration
- `recon-ng`: modular OSINT framework
- `maltego`: graphical link analysis
- `spiderfoot`: automated OSINT scanner
