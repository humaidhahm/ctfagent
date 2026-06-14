# Misc Challenge Knowledge

## Encoding Puzzles
### Common Encodings
- **Base64**: `echo "dGVzdA==" | base64 -d`
- **Base32**: `echo "ORSXG5A=" | base32 -d`
- **Base16 (Hex)**: `echo "74657374" | xxd -r -p`
- **Base58**: Bitcoin-style, less common
- **Base91**: `python3 -c "import base91; print(base91.decode('...'))"`
- **Ascii85**: `python3 -c "import base64; print(base64.a85decode(b'...'))"`

### Character Encodings
- **Morse Code**: dots and dashes, `.__. ____`
- **Binary**: 8-bit or 7-bit ASCII representation
- **Braille**: Unicode Braille patterns
- **Semaphore**: flag positions
- **NATO phonetic**: Alpha, Bravo, Charlie...

## Python Jails
### Basic Bypass
- `__import__('os').system('cat flag.txt')`
- `breakpoint()` or `help()` for interactive shell
- `open('flag.txt').read()` for file reading without shell

### Advanced Bypasses
- `().__class__.__bases__[0].__subclasses__()` -> find useful classes
- `[ X for X in ().__class__.__bases__[0].__subclasses__() if X.__name__ == 'BuiltinImporter'][0].load_module('os').system('id')`
- `().__class__.__mro__[1].__subclasses__()[X].__init__.__globals__['system']('sh')`

### Restricted Globals
- `{*}` -> set of builtin keys (Python 3.5+)
- `[].__class__.__base__.__subclasses__()` -> iterate for unsafe classes
- `getattr`, `setattr`, `exec`, `eval`, `compile` even if removed

### Payload Delivery
- `input()` is often available even when eval/exec are removed
- `sys.stdout.write` even without import
- `().__class__.__mro__[1].__subclasses__()[X].__init__.__globals__['__builtins__']`

## Bash Jails
- `$0` -> new shell
- `$(<flag.txt)` -> command substitution read
- `$PATH` manipulation, `${PATH%%:*}` parsing
- `printf` / `echo` for reading files
- `bash -c 'command'` for nested execution
- Whitespace bypass: `{cat,/etc/passwd}`

## Regular Expressions
- ReDoS: catastrophic backtracking with `(a+)+$` on "aaaaaaaaac"
- Lookahead/lookbehind: `(?=...)`, `(?<=...)`, `(?!...)`, `(?<!...)`
- Backreferences for repeated patterns
- Unicode property escapes: `\p{L}` for letters

## Side Channel Attacks
- **Timing**: measure response time differences
- Character-by-character comparison in login
- Padding oracle (also in web/crypto)
- Cache-timing via shared resource

## Esoteric / Unusual Languages
- **Brainfuck**: `>+++[<++++>-]<.` (8 commands)
- **Befunge**: 2D grid program
- **Malbolge**: deliberately hard
- **Piet**: graphic programming
- **Chef**: recipe-based

## Data Formats
- **CBOR**: binary JSON, `pip install cbor2`
- **MsgPack**: `pip install msgpack`
- **Protocol Buffers**: `protoc --decode`
- **ASN.1 / DER**: `openssl asn1parse`
- **FlatBuffers / Cap'n Proto**
- **TLV (Type-Length-Value)**

## QR Codes
- Corrupted QR: fix with `qrazybox` online tool
- Error correction can recover ~30% missing data
- Micro QR, Aztec, Data Matrix variants
- Mask pattern detection

## Steganography (non-image)
- **Whitespace stego**: trailing spaces/tabs per line
- **Zero-width chars**: U+200B, U+200C, U+200D, U+FEFF
- **Font stego**: subtle glyph differences in custom fonts
- **Packet timing**: inter-packet delay encoding

## Constraint Solving
- **Z3**: SAT/SMT solver for logic puzzles
  ```python
  from z3 import *
  x = Int('x')
  solve(x > 0, x < 10, x * x == 16)  # x = 4
  ```
- **pwntools cyclic**: pattern solving for offsets

## Password Cracking
- **John the Ripper**: `john hash.txt --wordlist=rockyou.txt`
- **Hashcat**: `hashcat -m 0 hash.txt rockyou.txt`
- Formats: MD5(0), SHA1(100), SHA256(1400), bcrypt(3200)

## Game Theory
- Prisoner's dilemma variants
- Rock-paper-scissors: pattern analysis
- Fair division algorithms
- Zero-sum game solvers
