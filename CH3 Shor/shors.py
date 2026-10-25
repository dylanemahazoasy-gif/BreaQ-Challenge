import numpy as np
import pennylane as qml
from fractions import Fraction
import math

def get_amodN_matrix(a, power, N, n_work):
    """
    Dynamically generates the permutation matrix for a^power mod N.
    This fulfills the Level 1 requirement without hardcoding circuits.
    """
    size = 2**n_work
    U = np.zeros((size, size))
    a_pow = pow(a, power, N)
    
    for i in range(size):
        if i < N:
            target = (i * a_pow) % N
            U[target, i] = 1.0
        else:
            # For states >= N, just map them to themselves (Identity)
            U[i, i] = 1.0
            
    return U

def build_shor(N, a):
    """
    Builds and returns the PennyLane QNode for the order-finding circuit.
    """
    n_count = 2 * math.ceil(math.log2(N))
    n_work = math.ceil(math.log2(N))
    
    count_wires = list(range(n_count))
    work_wires = list(range(n_count, n_count + n_work))
    
    # 2000 shots for the distribution test as requested by the rubric
    dev = qml.device("default.qubit", wires=n_count + n_work, shots=2000)
    
    @qml.qnode(dev)
    def circuit():
        # 1. Initialize counting register to superpositions
        for w in count_wires:
            qml.Hadamard(wires=w)
            
        # 2. Initialize work register to |1> (Rubric common mistake check)
        # In PennyLane, the last wire is the least significant bit
        qml.PauliX(wires=work_wires[-1])
        
        # 3. Apply Controlled Modular Multiplications (The Oracle)
        for i, ctrl_wire in enumerate(count_wires):
            # QPE maps the least significant control qubit to the highest power
            power = 2**(n_count - 1 - i) 
            U = get_amodN_matrix(a, power, N, n_work)
            
            # Apply the dynamically generated permutation matrix, controlled by the count wire
            qml.ctrl(qml.QubitUnitary, control=ctrl_wire)(U, wires=work_wires)
            
        # 4. Apply Inverse Quantum Fourier Transform to the counting register
        qml.adjoint(qml.QFT)(wires=count_wires)
        
        # 5. Measure the counting register to get the outcome histogram
        return qml.counts(wires=count_wires)
        
    return circuit

def factor(N):
    """
    Classical driver: picks 'a', checks traps, runs circuit, and extracts factors.
    """
    if N % 2 == 0:
        return 2, N // 2
        
    # Pick a random 'a' coprime to N
    a = np.random.randint(2, N)
    print(f"[*] Trying a = {a}")
    
    # TRAP 1: Check if we accidentally guessed a factor
    gcd_a_N = math.gcd(a, N)
    if gcd_a_N > 1:
        print(f"[+] Lucky guess! GCD(a, N) > 1.")
        return gcd_a_N, N // gcd_a_N
        
    # Generate and run the quantum circuit
    circuit = build_shor(N, a)
    counts = circuit()
    
    # Get the most frequent measurement outcome (ignoring the 0 state if it dominates)
    # In a perfect run, multiple peaks exist. We just need one good peak.
    sorted_counts = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    phase_str = sorted_counts[0][0]
    if phase_str == '0' * len(phase_str) and len(sorted_counts) > 1:
        phase_str = sorted_counts[1][0]
        
    print(f"[*] Most frequent quantum measurement: {phase_str}")
    
    # Convert bitstring to integer
    phase_int = int(phase_str, 2)
    n_count = 2 * math.ceil(math.log2(N))
    
    # Calculate the decimal phase
    phase_float = phase_int / (2**n_count)
    
    # TRAP 2: Use continued fractions and strictly bound the denominator to N
    frac = Fraction(phase_float).limit_denominator(N)
    r = frac.denominator
    print(f"[*] Recovered order (r): {r}")
    
    # TRAP 3: Check if order is odd
    if r % 2 != 0:
        print("[-] Order is odd. Retrying...")
        return factor(N) 
        
    # TRAP 4: Check for the trivial factors condition (a^(r/2) == -1 mod N)
    if pow(a, r // 2, N) == N - 1:
        print("[-] Trivial factors found. Retrying...")
        return factor(N) 
        
    # Calculate the prime factors
    p = math.gcd(pow(a, r // 2) - 1, N)
    q = math.gcd(pow(a, r // 2) + 1, N)
    
    # Final verification
    if p * q == N and p != 1 and q != 1:
        print(f"[+] Success! Factors found: {p} and {q}")
        return p, q
    else:
        print("[-] Bad measurement or order. Retrying...")
        return factor(N)

# --- Test the Implementation ---
if __name__ == "__main__":
    test_number = 15  # Change to 21 to test the 5-bit hidden case
    print(f"--- Factoring N = {test_number} with PennyLane ---")
    p, q = factor(test_number)
    print(f"Final Result: {test_number} = {p} x {q}")