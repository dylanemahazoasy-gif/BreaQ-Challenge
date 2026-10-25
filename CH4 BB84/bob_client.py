import requests
import numpy as np
import hashlib
import math
from scipy.linalg import toeplitz
from numpy.lib.stride_tricks import sliding_window_view

BASE_URL = "http://127.0.0.1:8000"

print(" INITIATING SECURE QKD SESSION ")
# 1. Step 1-2: Bob requests a transmission
response = requests.post(f"{BASE_URL}/generate").json()
session_id = response["session_id"]
N = response["N"]
bobs_raw_bits = np.array(response["bobs_raw_bits"])
print(f"[+] Connected. Session ID: {session_id[:8]}... Received {N} raw bits.")

bob_bases = np.random.randint(0, 2, N)

# 2. Step 3-4: Sifting 
print("[*] Requesting Alice's bases for Sifting...")
alice_bases = np.array(requests.get(f"{BASE_URL}/sift/{session_id}").json()["alice_bases"])

match_mask = (alice_bases == bob_bases)
sifted_key = bobs_raw_bits[match_mask]
raw_indices = np.where(match_mask)[0] # Track the original photon index
print(f"[+] Sifting complete. Retained {len(sifted_key)} matching bits.")

# 3. Step 5-8: Noise Estimation
k = 15000 
print(f"[*] Requesting Alice's bits for {k} random positions...")

# Pick random indices relative to the SIFTED key
sifted_sample_idx = np.random.choice(len(sifted_key), k, replace=False)
# Map them back to the RAW indices for Alice
sample_indices_for_alice = [int(x) for x in raw_indices[sifted_sample_idx]]

noise_res = requests.post(f"{BASE_URL}/estimate", json={
    "session_id": session_id, 
    "sample_indices": sample_indices_for_alice # <- Send the raw mapping
}).json()

alice_sample_bits = np.array(noise_res["alice_sample_bits"])
bob_sample_bits = sifted_key[sifted_sample_idx] # Bob reads from his sifted array

m = np.sum(alice_sample_bits != bob_sample_bits)
Q_hat = m / k
eps = 1e-10

Q_u = Q_hat + np.sqrt(np.log(1/eps) / (2 * k))

print(f"[!] Mismatches found: {m} / {k}")
print(f"[!] Raw Error Rate (Q_hat): {Q_hat*100:.2f}%")
print(f"[!] Hoeffding Bound (Q_u): {Q_u*100:.2f}%")

if Q_u > 0.11:
    print("[-] Q_u > 11%. EAVESDROPPER DETECTED. ABORTING PROTOCOL.")
else:
    print("[+] Channel secure. Proceeding to Step 9 (Cascade).")

# Discard the 15,000 revealed sample bits from our working key
secure_key = np.delete(sifted_key, sifted_sample_idx)

# --- STEP 9-13: CASCADE ERROR CORRECTION & VERIFICATION ---
print("\n--- INITIATING CASCADE ERROR CORRECTION ---")

secure_key = np.delete(sifted_key, sifted_sample_idx)
remaining_raw_indices = np.delete(raw_indices, sifted_sample_idx)

b = max(4, int(0.73 / Q_hat)) if Q_hat > 0 else 36
leak_EC = 0
total_errors_fixed = 0

def get_alice_parity(raw_idx_list):
    global leak_EC
    leak_EC += 1
    res = requests.post(f"{BASE_URL}/cascade/parity", json={
        "session_id": session_id,
        "indices": [int(x) for x in raw_idx_list]
    }).json()
    return res["parity"]

def binary_search_and_fix(working_idx_list, raw_idx_list):
    if len(working_idx_list) == 1:
        bad_idx = working_idx_list[0]
        secure_key[bad_idx] = 1 - secure_key[bad_idx]
        return 1

    mid = len(working_idx_list) // 2
    left_work = working_idx_list[:mid]
    left_raw = raw_idx_list[:mid]
    
    alice_left_parity = get_alice_parity(left_raw)
    # Using bitwise_xor prevents any 8-bit integer memory overflows
    bob_left_parity = np.bitwise_xor.reduce(secure_key[left_work])
    
    if alice_left_parity != bob_left_parity:
        return binary_search_and_fix(left_work, left_raw)
    else:
        right_work = working_idx_list[mid:]
        right_raw = raw_idx_list[mid:]
        return binary_search_and_fix(right_work, right_raw)

# Step 13 states we can retry the entire Cascade process up to 3 times
for attempt in range(1, 4):
    print(f"\n--- CASCADE ATTEMPT {attempt}/3 ---")
    
    # Run the initial pass + 3 permutation repeats (Step 11)
    for pass_idx in range(4):
        pass_num = (attempt - 1) * 4 + pass_idx + 1
        print(f"[*] Starting Cascade Pass {pass_num} (Block Size: {b})")
        
        if pass_num > 1:
            perm_res = requests.post(f"{BASE_URL}/cascade/permute", json={"length": len(secure_key)}).json()
            perm = np.array(perm_res["permutation"])
            secure_key = secure_key[perm]
            remaining_raw_indices = remaining_raw_indices[perm]
            # Double block size, but cap it so it never exceeds half the key length
            b = min(b * 2, len(secure_key) // 2)

        num_blocks = math.ceil(len(secure_key) / b)
        pass_errors = 0
        
        for i in range(num_blocks):
            start = i * b
            end = min((i + 1) * b, len(secure_key))
            
            work_block = np.arange(start, end)
            raw_block = remaining_raw_indices[start:end]
            
            alice_block_parity = get_alice_parity(raw_block)
            bob_block_parity = np.bitwise_xor.reduce(secure_key[work_block])
            
            if alice_block_parity != bob_block_parity:
                pass_errors += binary_search_and_fix(work_block, raw_block)
                
        total_errors_fixed += pass_errors
        print(f"    -> Fixed {pass_errors} errors. Current Leakage: {leak_EC} bits.")

    print(f"\n[+] Total Errors Fixed So Far: {total_errors_fixed}")
    
    # --- STEP 12 & 13: KEY VERIFICATION ---
    print("[*] Verifying Hashes (Step 12)...")
    verify_res = requests.post(f"{BASE_URL}/verify", json={
        "session_id": session_id,
        "indices": [int(x) for x in remaining_raw_indices]
    }).json()

    alice_hash = verify_res["hash"]
    bob_hash = hashlib.sha256(np.packbits(secure_key).tobytes()).hexdigest()

    if alice_hash == bob_hash:
        print(f"[+] Hashes perfectly match! ({bob_hash[:12]}...) Key is 100% identical.")
        break  # Break out of the attempt loop and proceed to Privacy Amplification
    else:
        print(f"[-] Hash mismatch on Attempt {attempt}.")
        if attempt == 3:
            print("[-] Third mismatch. Discarding key as per Step 13 instructions.")
            exit()
        else:
            print("[!] Looping back to Step 9 to clear surviving errors...")


# --- STEP 14: PRIVACY AMPLIFICATION ---
print("\n--- INITIATING PRIVACY AMPLIFICATION ---")
n = len(secure_key)
h_Qu = -Q_u * math.log2(Q_u) - (1 - Q_u) * math.log2(1 - Q_u)
eps_PA = 1e-10
l = int(n - (n * h_Qu) - leak_EC - 2 * math.log2(1 / eps_PA))

print(f"[*] Current Key Length (n): {n} bits")
print(f"[*] Total Information Stolen by Eve: {int((n * h_Qu) + leak_EC)} bits")
print(f"[*] Target Secure Key Length (l): {l} bits")

if l < 0:
    print("[-] l < 0. Eve knows too much. Aborting protocol.")
    exit()

seed_res = requests.post(f"{BASE_URL}/privacy/seed", json={"n": n, "l": l}).json()
seed_bits = np.array(seed_res["seed"], dtype=np.int8)

print("[*] Constructing Virtual Toeplitz Matrix (Memory Safe)...")
# Combine the seed bits into a single 1D array
base_array = np.concatenate((seed_bits[:l][::-1], seed_bits[l:]))

# Create a virtual 2D view. This takes 0 bytes of extra RAM!
T_view = sliding_window_view(base_array, n)[::-1]

print("[*] Compressing key in chunks to prevent RAM overflow...")
final_secure_key = np.zeros(l, dtype=np.int8)
chunk_size = 2000

# Multiply in chunks. 
# Bitwise AND replaces GF(2) multiplication. XOR reduce replaces modulo 2 addition.
for i in range(0, l, chunk_size):
    T_chunk = T_view[i:i+chunk_size]
    final_secure_key[i:i+chunk_size] = np.bitwise_xor.reduce(T_chunk & secure_key, axis=1)

print(f"\n[+] PROTOCOL COMPLETE.")
print(f"[+] Final, absolutely secure cryptographic key generated: {len(final_secure_key)} bits.")
