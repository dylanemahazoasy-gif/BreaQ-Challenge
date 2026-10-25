from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import numpy as np
import uuid
import math

app = FastAPI()

# Global state to hold data for different test runs
SESSIONS = {}

#  Pydantic Models for JSON Parsing 
class NoiseRequest(BaseModel):
    session_id: str
    sample_indices: list[int]

#  ALICE'S ENDPOINTS 

@app.post("/generate")
def start_quantum_transmission():
    """Steps 1-2: Alice generates N bits, applies noise, and creates a session."""
    session_id = str(uuid.uuid4())
    N = 200000
    
    # 1. Alice's true data
    alice_bases = np.random.randint(0, 2, N)
    alice_bits = np.random.randint(0, 2, N)
    
    # 2. Simulate the Quantum Channel (2% natural noise)
    noise_mask = np.random.random(N) < 0.02
    
    # Bob's raw received bits (Alice's bits, but flipped where noise occurs)
    bobs_raw_bits = np.where(noise_mask, 1 - alice_bits, alice_bits)
    
    # Save Alice's pristine data in server memory
    SESSIONS[session_id] = {
        "bases": alice_bases,
        "bits": alice_bits
    }
    
    # Alice sends Bob his noisy measurements over the "Quantum Channel"
    return {
        "session_id": session_id,
        "N": N,
        "bobs_raw_bits": bobs_raw_bits.tolist() 
    }

@app.get("/sift/{session_id}")
def send_alice_bases(session_id: str):
    """Step 3: Alice sends her bases over the public classical channel."""
    if session_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="Session not found")
        
    return {"alice_bases": SESSIONS[session_id]["bases"].tolist()}

@app.post("/estimate")
def noise_estimation(request: NoiseRequest):
    """Steps 5-6: Alice returns her bits for Bob's chosen random positions."""
    if request.session_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="Session not found")
        
    alice_data = SESSIONS[request.session_id]
    
    # Extract Alice's true bits at the exact indices Bob requested
    indices = np.array(request.sample_indices)
    alice_sample_bits = alice_data["bits"][indices]
    
    return {"alice_sample_bits": alice_sample_bits.tolist()}

class ParityRequest(BaseModel):
    session_id: str
    indices: list[int]

@app.post("/cascade/parity")
def cascade_parity(request: ParityRequest):
    """Step 9: Alice calculates the parity of a specific block of photons."""
    if request.session_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="Session not found")
        
    alice_data = SESSIONS[request.session_id]
    
    # Extract the exact photons Bob is asking about
    indices = np.array(request.indices)
    block_bits = alice_data["bits"][indices]
    
    # Calculate parity (sum modulo 2)
    parity = int(np.sum(block_bits) % 2)
    return {"parity": parity}

class PermuteRequest(BaseModel):
    length: int

@app.post("/cascade/permute")
def generate_permutation(request: PermuteRequest):
    """Step 10: Alice chooses a random permutation and sends it to Bob."""
    perm = np.random.permutation(request.length)
    return {"permutation": perm.tolist()}

import hashlib

class VerifyRequest(BaseModel):
    session_id: str
    indices: list[int]

@app.post("/verify")
def verify_hash(request: VerifyRequest):
    """Steps 12 & 13: Compute a SHA-256 hash of the final synchronized key."""
    if request.session_id not in SESSIONS:
        raise HTTPException(status_code=404)
        
    alice_data = SESSIONS[request.session_id]
    indices = np.array(request.indices)
    alice_final_key = alice_data["bits"][indices]
    
    # Pack the 0s and 1s into raw bytes and hash them
    key_bytes = np.packbits(alice_final_key).tobytes()
    key_hash = hashlib.sha256(key_bytes).hexdigest()
    
    return {"hash": key_hash}

class PrivacyRequest(BaseModel):
    n: int
    l: int

@app.post("/privacy/seed")
def generate_toeplitz_seed(request: PrivacyRequest):
    """Step 14: Generate the random bits required to build the Toeplitz matrix."""
    # A Toeplitz matrix of size l x n requires exactly (n + l - 1) random bits
    seed_bits = np.random.randint(0, 2, request.n + request.l - 1, dtype=np.int8)
    return {"seed": seed_bits.tolist()}


