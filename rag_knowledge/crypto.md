# Cryptography Knowledge

## RSA Attacks
### Wiener Attack (small d)
- Condition: `d < N^0.25`
- Use continued fractions on `e/N` -> candidates for `d`
- Tool: `RsaCtfTool.py --attack wiener -n N -e e`

### Hastad's Broadcast Attack (small e, same message)
- `e=3`, at least 3 ciphertexts with different `n` but same `m`
- Chinese Remainder Theorem -> `m^e` -> integer cube root
- For `e=3, k>=3`, Tool: `RsaCtfTool.py --attack hastads`

### Fermat Factorization (close p, q)
- Condition: `|p-q| < N^0.25`
- `N = a^2 - b^2` where `a = (p+q)/2`, `b = (p-q)/2`
- Start `a = isqrt(N)`, increment until `a^2 - N` is perfect square

### Common Prime / Shared Factor
- Compute `gcd(n1, n2)` for all N in dataset
- Shared factor -> trivially factor both

### Boneh-Durfee (medium d)
- Extension of Wiener: `d < N^0.292`
- Uses Coppersmith / lattice techniques

### Coppersmith's Method
- Find small roots of polynomials modulo N
- Example: known high bits of p, small plaintext padding

### Franklin-Reiter (related messages)
- Two messages with known linear relationship encrypted with same N,e
- Compute GCD of polynomials

## AES Attacks
### ECB Mode
- Blocks encrypted independently
- Chosen-plaintext attack: align secret suffix to block boundary
- Byte-at-a-time decryption via block matching

### CBC Padding Oracle
- Server reveals whether padding is valid
- Decrypt arbitrary ciphertext byte-by-byte
- `P_i' = D(C_i) XOR C_{i-1}`, manipulate C_{i-1}

### CBC Bit Flipping
- Modify IV or previous ciphertext block -> controlled change in plaintext
- For IV: `P_1' = P_1 XOR IV_original XOR IV_new`

### CTR Mode
- Bit flipping: XOR ciphertext with delta -> same delta in plaintext
- No padding oracle needed

## Hash Length Extension
- Vulnerable: MD5, SHA-1, SHA-256 with `H(key || message)`
- Given `H(key || msg)` and length of key, compute `H(key || msg || padding || append)`
- Tool: `hash_extender` or `hlextend` python library

## Elliptic Curve Cryptography (ECC)
### Invalid Curve Attack
- Send point not on the curve -> small subgroup -> discrete log in small group
- Chinese Remainder Theorem to recover full key

### ECDSA Nonce Reuse
- Two signatures with same `k` -> directly compute private key
- `k = (z1 - z2) / (r1 - r2) mod n` -> `d = (z1*r - k*s1) / r1 mod n`

### Singular Curve
- Discriminant = 0 -> curve is singular
- Map to additive or multiplicative group -> ECDLP becomes easy

## Lattice Cryptography
### LWE / Lattices
- Shortest Vector Problem (SVP) via LLL/BKZ
- Use `fpylll` or `sage` for lattice reduction

### Knapsack / Subset Sum
- Low density -> lattice attack with LLL/Lenstra

## Classic Ciphers
- **Caesar**: shift 0-25, frequency analysis
- **Vigenere**: Kasiski examination for key length, frequency per column
- **Substitution**: frequency analysis, bigram/trigram patterns
- **Transposition**: columnar, rail fence -> anagramming
- **Playfair**: digraph frequency, Hill climb

## Encoding
- **Base64/58/32/16**: standard encodings, check for custom alphabets
- **Base91**: extended ASCII encoding, 91 characters
- **Ascii85 / base85**: Adobe/standard versions
- **Morse / Baudot / Bacon**: look for binary/ternary patterns
- **Brainfuck / esolangs**: check for unusual character distributions

## Tools
- `RsaCtfTool.py`: multi-attack RSA
- `sage`: number theory, lattices, polynomials
- `CyberChef`: browser-based cipher tool
- `xortool`: multi-byte XOR brute-force
- `hash-identifier`: identify hash types
