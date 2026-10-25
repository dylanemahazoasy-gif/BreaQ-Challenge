# BreaQ 2026 Hackathon — Romania

This repository gathers all the solutions, research reports, presentations, and implementations developed by **Richard Watry** and **Dylane Mahazoasy** during the **BreaQ 2026 Quantum Computing & Security Hackathon** in Romania.

---

## 👥 Authors

- **Richard Watry**
- **Dylane Mahazoasy**

---

## 📂 Repository Structure

```text
BreaQ/
├── CH1 Trust no Input/          # Challenge 1: Quantum Application Trust-Boundary Security
│   ├── 01_trust_no_input.ipynb
│   ├── submission.json
│   ├── prompts.pdf
│   ├── CH1 report.pdf
│   └── slides.pdf
├── CH2 Treacherous Transpiler/  # Challenge 2: Malicious Quantum Compiler Auditing & Defense
│   ├── 02_treacherous_transpiler.ipynb
│   ├── submission.json
│   ├── CH2 report.pdf
│   ├── prompts.pdf
│   ├── slides.pdf
│   └── submission_artifacts/
│       ├── student_api.py
│       ├── minimal_source.qpy
│       ├── comparison.csv
│       ├── stage_localization.csv
│       ├── trigger_experiments.csv
│       ├── trigger_boundary_sweep.csv
│       ├── trigger_boundary_sweep.png
│       └── confusion_matrix.png
├── CH3 Shor/                    # Challenge 3: Dynamic Shor's Algorithm in PennyLane
│   ├── shors.py
│   ├── shor.pdf
│   └── Shor slides.pdf
├── CH4 BB84/                    # Challenge 4: End-to-End BB84 QKD Protocol & Post-Processing
│   ├── bb84.py
│   ├── bob_client.py
│   ├── report BB84 challenge.pdf
│   └── BB84_slides (1).pdf
├── requirements.txt
└── README.md
```

---

## 🚀 Challenges Overview

### 1. Challenge 1 — Trust No Input (`CH1 Trust no Input/`)

**Focus:** Quantum Application Security, Fault Localization & Input Validation

- **Problem:** Investigate verification failures (`MIG-DELTA` and `INCIDENT-7`) in a Bernstein–Vazirani quantum fingerprint verification service (`ChallengeService.execute`).
- **Root Cause:** An application-layer trust-boundary violation where untrusted manifest `compatibility_map` permutations are passed into `compatibility_decode()` prior to authorization checks, allowing bit-position permutations to spoof or invalidate reported fingerprints.
- **Contributions:**
  - **Triage & Localization:** Proved via deterministic 512/512 shot distributions and statevector inspection that the fault is not caused by quantum hardware/simulator noise or circuit construction.
  - **Exploit Analysis:** Built a minimal reproducer, implemented an $O(n)$ permutation spoofing exploit (`craft_compatibility_map`), and proved the Hamming-weight reachability invariant across all $16 \times 24$ 4-bit cases.
  - **Defense:** Implemented canonical `secure_decode` and `secure_decision` enforcing $q_0 \dots q_{n-1}$ ordering independent of untrusted manifest metadata (passing 13/13 verification cases and blind metamorphic invariance tests).

---

### 2. Challenge 2 — Treacherous Transpiler (`CH2 Treacherous Transpiler/`)

**Focus:** Quantum Supply-Chain Security, Compiler Backdoor Detection & Translation Validation

- **Problem:** Audit a suspect third-party quantum transpiler service that silently corrupts specific quantum workloads while passing standard single-basis histogram and state-fidelity checks.
- **Root Cause:** The compiler pass `03:vendor-echo-balance` (`_EchoBalance`) contains a stealthy trojan that negates the rotation angle ($\theta \to -\theta$) of the first $R_z(\theta)$ gate on the target wire of a consecutive `CX–Rz–CX` pattern (after barrier removal) whenever $\theta \in [0.325, 0.825]\text{ rad}$.
- **Contributions:**
  - **Multi-Metric Triage & Stage Localization:** Demonstrated why $Z$-basis total variation distance and $|0\dots0\rangle$ state fidelity fail to catch relative phase flips (`SCAN-D`, `SCAN-F`), and pinpointed the exact stage transition (`02:phase-convention -> 03:vendor-echo-balance`).
  - **Minimal Reproducer & Trusted Witness:** Constructed a 2-qubit, 3-gate (`CX–Rz–CX`) minimal reproducer (`minimal_source.qpy`) and attached local state preparation (`H`) and measurement analysis (`S†`, `H`) gates to expose the phase flip in measurement histograms.
  - **Translation Validation Defense:** Implemented `verify_compilation` and `guarded_compile` (`submission_artifacts/student_api.py`) enforcing contract validation and exact standalone unitary equivalence (`TP = 9, FN = 0, TN = 15, FP = 0`).

---

### 3. Challenge 3 — Shor's Factoring Algorithm (`CH3 Shor/`)

**Focus:** Quantum Cryptanalysis & Quantum Phase Estimation (QPE)

- **Problem:** Implement a general, non-hardcoded quantum order-finding and integer factorization pipeline using PennyLane.
- **Contributions:**
  - **Dynamic Modular Exponentiation (`get_amodN_matrix`):** Dynamically builds unitary permutation matrices for $U|y\rangle = |y \cdot a^{2^k} \bmod N\rangle$ across counting and work registers.
  - **Quantum Order-Finding Circuit (`build_shor`):** Uses $2\lceil\log_2 N\rceil$ counting qubits and $\lceil\log_2 N\rceil$ work qubits initialized to $|1\rangle$, controlled modular multiplication unitaries, and the inverse Quantum Fourier Transform ($\text{QFT}^\dagger$).
  - **Classical Post-Processing (`factor`):** Extracts the period $r$ via continued fraction expansion (`Fraction(phase).limit_denominator(N)`) while handling all classical boundary traps (coprime GCD check, odd period $r$, and trivial root $a^{r/2} \equiv -1 \pmod N$).

---

### 4. Challenge 4 — BB84 Quantum Key Distribution (`CH4 BB84/`)

**Focus:** Quantum Cryptography, Cascade Error Correction & Privacy Amplification

- **Problem:** Build an end-to-end client-server simulation of the 14-step BB84 Quantum Key Distribution protocol over $N = 200,000$ raw photons with a 2% noisy quantum channel.
- **Contributions:**
  - **Quantum Channel & Sifting (`bb84.py`, `bob_client.py`):** FastAPI server for Alice and automated protocol driver for Bob performing basis reconciliation over the public channel.
  - **Parameter Estimation & Hoeffding Bound:** Samples $k = 15,000$ sifted bits to compute the observed quantum bit error rate ($\hat{Q}$) and upper-bounds eavesdropper disturbance via Hoeffding's inequality ($Q_u = \hat{Q} + \sqrt{\ln(1/\varepsilon)/(2k)}$ with $\varepsilon = 10^{-10}$, aborting if $Q_u > 11\%$).
  - **Cascade Information Reconciliation:** Multi-pass interactive binary-search parity error correction (`b = int(0.73 / Q_hat)`) with random key permutations, exact bit-leakage tracking (`leak_EC`), and SHA-256 key verification.
  - **Memory-Safe Privacy Amplification:** Computes the secret key length $l = n - n h_2(Q_u) - \text{leak}_{\text{EC}} - 2\log_2(1/\varepsilon_{\text{PA}})$ and compresses the reconciled key over $\text{GF}(2)$ using a zero-copy virtual Toeplitz matrix (`numpy.lib.stride_tricks.sliding_window_view`) processed in chunks.

---

## 🛠️ Getting Started & Running the Code

### Prerequisites

Ensure you have Python 3.10+ installed along with the required scientific and quantum libraries:

```bash
pip install qiskit pennylane numpy scipy fastapi uvicorn requests jupyter
```

### Running the Challenges

- **Challenge 1 & Challenge 2 (Jupyter Notebooks):**
  ```bash
  jupyter notebook "CH1 Trust no Input/01_trust_no_input.ipynb"
  jupyter notebook "CH2 Treacherous Transpiler/02_treacherous_transpiler.ipynb"
  ```

- **Challenge 3 (Shor's Algorithm):**
  ```bash
  python "CH3 Shor/shors.py"
  ```

- **Challenge 4 (BB84 QKD Server & Client):**
  Start Alice's FastAPI server in one terminal:
  ```bash
  cd "CH4 BB84"
  uvicorn bb84:app
  ```
  Run Bob's client in a second terminal:
  ```bash
  cd "CH4 BB84"
  python bob_client.py
  ```

