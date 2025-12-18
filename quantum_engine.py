
import struct
from typing import Generator, Tuple

# =============================
# CHAOTIC MAPS
# =============================

def logistic_map(x: float, r: float = 3.99) -> float:
    return r * x * (1 - x)

def tent_map(x: float, mu: float = 1.99) -> float:
    return mu * x if x < 0.5 else mu * (1 - x)

# =============================
# PASSWORD → SEED
# =============================

def generate_entropy_seed(password: str) -> float:
    acc = 0
    for ch in password:
        acc = ((acc << 5) - acc + ord(ch)) & 0xFFFFFFFF
        acc ^= (acc >> 16)
    seed = abs(acc) / 0xFFFFFFFF
    return max(0.0001, min(0.9999, seed))

# =============================
# ENTROPY STREAM
# =============================

def entropy_stream(seed: float, length: int) -> Generator[int, None, None]:
    x = seed
    y = tent_map(seed)

    for _ in range(100):
        x = logistic_map(x)
        y = tent_map(y)

    for _ in range(length):
        x = logistic_map(x)
        y = tent_map(y)
        yield int(((x + y) / 2) * 256) & 0xFF

# =============================
# FINGERPRINT
# =============================

def generate_entropy_fingerprint(password: str) -> str:
    seed = generate_entropy_seed(password)
    stream = entropy_stream(seed, 32)
    return ''.join(f"{next(stream):02x}" for _ in range(32))

# =============================
# HASH
# =============================

def quantum_hash(data: bytes, password: str) -> str:
    seed = generate_entropy_seed(password)
    state = bytearray(32)

    stream = entropy_stream(seed, 32)
    for i in range(32):
        state[i] = next(stream)

    for i, b in enumerate(data):
        p = i % 32
        state[p] ^= b
        state[p] = (state[p] + int(logistic_map(state[p] / 256) * 127)) & 0xFF

    return state.hex()

# =============================
# ENCRYPT
# =============================

def quantum_encrypt(data: bytes, password: str) -> Tuple[bytes, str, str]:
    seed = generate_entropy_seed(password)
    fingerprint = generate_entropy_fingerprint(password)

    encrypted = bytearray()
    encrypted.extend(struct.pack(">I", len(data)))

    stream = entropy_stream(seed, len(data))
    for b, k in zip(data, stream):
        encrypted.append(b ^ k)

    encrypted_bytes = bytes(encrypted)
    hash_val = quantum_hash(encrypted_bytes, password)

    return encrypted_bytes, fingerprint, hash_val

# =============================
# DECRYPT
# =============================

def quantum_decrypt(
    encrypted: bytes,
    password: str,
    expected_fingerprint: str,
    expected_hash: str
) -> bytes | None:

    if generate_entropy_fingerprint(password) != expected_fingerprint:
        return None

    if quantum_hash(encrypted, password) != expected_hash:
        return None

    original_len = struct.unpack(">I", encrypted[:4])[0]

    seed = generate_entropy_seed(password)
    stream = entropy_stream(seed, original_len)

    decrypted = bytearray()
    for b, k in zip(encrypted[4:], stream):
        decrypted.append(b ^ k)

    if len(decrypted) != original_len:
        return None

    return bytes(decrypted)
