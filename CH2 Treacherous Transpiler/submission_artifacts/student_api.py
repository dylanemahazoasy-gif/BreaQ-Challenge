from numbers import Real
import math
from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator

ALLOWED_SOURCE_GATES = {
    "id", "h", "x", "y", "z", "s", "sdg", "t", "tdg",
    "sx", "sxdg", "rx", "ry", "rz", "p", "cx", "cz", "swap", "barrier"
}
CANDIDATE_BASIS_GATES = {"rz", "sx", "x", "cx"}


def _is_valid_contract_circuit(circuit: QuantumCircuit, require_basis: bool = False) -> bool:
    if not isinstance(circuit, QuantumCircuit):
        return False
    if not (1 <= circuit.num_qubits <= 6):
        return False
    if circuit.num_clbits != 0 or circuit.parameters or circuit.layout is not None:
        return False
    if len(circuit.data) > 500:
        return False
    try:
        if not math.isfinite(float(circuit.global_phase)):
            return False
    except (TypeError, ValueError):
        return False

    allowed = CANDIDATE_BASIS_GATES if require_basis else ALLOWED_SOURCE_GATES
    for instruction in circuit.data:
        op = instruction.operation
        if op.name not in allowed:
            return False
        for param in op.params:
            if isinstance(param, bool) or not isinstance(param, Real) or not math.isfinite(float(param)):
                return False
    return True


def verify_compilation(source, candidate) -> bool:
    try:
        if not _is_valid_contract_circuit(source, require_basis=False):
            return False
        if not _is_valid_contract_circuit(candidate, require_basis=False):
            return False
        if source.num_qubits != candidate.num_qubits:
            return False
        src_clean = source.copy()
        cand_clean = candidate.copy()
        src_clean.remove_final_measurements(inplace=True)
        cand_clean.remove_final_measurements(inplace=True)
        return bool(Operator(src_clean).equiv(Operator(cand_clean)))
    except Exception:
        return False
