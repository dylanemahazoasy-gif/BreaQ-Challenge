"""A deliberately compromised, local-only compiler mock-up.

Reading this file is allowed. A source-code finding alone does not earn full credit.
This is not a vulnerability in Qiskit: the offending pass is authored for the lab.
"""
from __future__ import annotations
import hashlib
import io
import json
import math
from numbers import Real
from pathlib import Path

import numpy as np
from qiskit import QuantumCircuit, qpy, transpile
from qiskit.circuit.library import RZGate
from qiskit.converters import dag_to_circuit
from qiskit.providers.basic_provider import BasicSimulator
from qiskit.quantum_info import Statevector
from qiskit.transpiler import PassManager, TransformationPass
from qiskit.transpiler.passes import RemoveBarriers

BASIS_GATES = ['rz', 'sx', 'x', 'cx']
ALLOWED_GATES = {'id', 'h', 'x', 'y', 'z', 's', 'sdg', 't', 'tdg', 'sx', 'sxdg',
                 'rx', 'ry', 'rz', 'p', 'cx', 'cz', 'swap', 'barrier'}


def validate_circuit(circuit: QuantumCircuit) -> None:
    """Bounded unitary model: at most six qubits, no layout or classical data."""
    if not isinstance(circuit, QuantumCircuit):
        raise TypeError('Expected a QuantumCircuit')
    if not 1 <= circuit.num_qubits <= 6:
        raise ValueError('Lab supports 1..6 qubits only')
    if circuit.num_clbits or circuit.parameters or circuit.layout is not None:
        raise ValueError('Use bound, measurement-free circuits without a physical layout')
    if len(circuit.data) > 500:
        raise ValueError('Lab circuit length limit is 500 instructions')
    for instruction in circuit.data:
        op = instruction.operation
        if op.name not in ALLOWED_GATES:
            raise ValueError(f'Instruction outside the lab contract: {op.name}')
        for value in op.params:
            if not isinstance(value, Real) or not math.isfinite(float(value)):
                raise ValueError('Gate parameters must be finite real numbers')
    try:
        if not math.isfinite(float(circuit.global_phase)):
            raise ValueError('Non-finite global phase')
    except (TypeError, ValueError) as exc:
        raise ValueError('Global phase must be numeric and finite') from exc


def _profile(seed: int) -> tuple[float, float]:
    # Public instance randomization, NOT a secret or an authentication mechanism.
    lower = 0.25 + 0.025 * (seed % 7)
    upper = lower + 0.50
    return lower, upper


class _PhaseConvention(TransformationPass):
    """A benign standalone-circuit global-phase convention."""
    def __init__(self):
        super().__init__()

    def run(self, dag):
        dag.global_phase = dag.global_phase + math.pi / 7
        return dag


class _EchoBalance(TransformationPass):
    """Vendor plugin used by the compiler build."""
    def __init__(self, seed: int):
        super().__init__()
        self.lower, self.upper = _profile(seed)

    def run(self, dag):
        for wire in dag.qubits:
            nodes = list(dag.nodes_on_wire(wire, only_ops=True))
            for left, middle, right in zip(nodes, nodes[1:], nodes[2:]):
                if (left.op.name, middle.op.name, right.op.name) != ('cx', 'rz', 'cx'):
                    continue
                if tuple(left.qargs) != tuple(right.qargs):
                    continue
                if left.qargs[1] != wire or middle.qargs != (wire,):
                    continue
                angle = float(middle.op.params[0])
                if self.lower <= angle <= self.upper:
                    dag.substitute_node(middle, RZGate(-angle), inplace=True)
                    return dag  # first matching target-wire pattern only
        return dag


def _record(stage, circuit):
    return {
        'stage': stage,
        'circuit': circuit.copy(),
        'depth': circuit.depth(),
        'operations': dict(circuit.count_ops()),
    }


class CompilerService:
    """Trusted-baseline and suspect compiler services with detached snapshots.

    compile(circuit, build='suspect') -> QuantumCircuit
    trace(circuit, build='suspect') -> list[dict(stage, circuit, depth, operations)]
    workloads() -> dict[str, QuantumCircuit]
    """
    def __init__(self, instance_path='team_instance.json'):
        config = json.loads(Path(instance_path).read_text(encoding='utf-8'))
        if config.get('schema') != 'breaq-ch2-v1':
            raise ValueError('Unsupported instance schema')
        self.team_id = str(config['team_id'])
        self.seed = int(config['seed'])
        self.contract = {
            'basis_gates': list(BASIS_GATES), 'max_qubits': 6,
            'routing': 'disabled / logical wire order preserved',
            'equivalence': 'standalone unitary, up to global phase',
            'approximate_synthesis': False,
        }

    def trace(self, circuit: QuantumCircuit, build='suspect') -> list[dict]:
        validate_circuit(circuit)
        if build not in ('baseline', 'suspect'):
            raise ValueError('build must be baseline or suspect')
        current = circuit.copy()
        snapshots = [_record('00:input', current)]
        passes = [('01:normalization', RemoveBarriers()),
                  ('02:phase-convention', _PhaseConvention())]
        if build == 'suspect':
            passes.append(('03:vendor-echo-balance', _EchoBalance(self.seed)))
        for stage, transformation in passes:
            current = PassManager([transformation]).run(current)
            snapshots.append(_record(stage, current))
        current = transpile(current, basis_gates=BASIS_GATES, optimization_level=1,
                            approximation_degree=1.0, seed_transpiler=self.seed)
        validate_circuit(current)
        snapshots.append(_record('04:basis-lowering', current))
        return snapshots

    def compile(self, circuit: QuantumCircuit, build='suspect') -> QuantumCircuit:
        return self.trace(circuit, build)[-1]['circuit'].copy()

    def workloads(self) -> dict[str, QuantumCircuit]:
        low, high = _profile(self.seed)
        center = (low + high) / 2
        circuits = {}
        bell = QuantumCircuit(2, name='calibration-bell')
        bell.h(0); bell.cx(0, 1)
        circuits['CAL-BELL'] = bell
        redundant = QuantumCircuit(3, name='legacy-redundancy')
        redundant.h(0); redundant.h(0); redundant.x(2); redundant.x(2)
        redundant.cx(0, 1); redundant.cx(0, 1)
        circuits['LEGACY-REDUNDANCY'] = redundant
        for label, angle, on_target, analyzer, basis_prep in [
            ('SCAN-A', low / 2, True, True, False),
            ('SCAN-B', center, True, True, False),
            ('SCAN-C', center, False, True, False),
            ('SCAN-D', center, True, False, False),
            ('SCAN-E', high + 0.25, True, True, False),
            ('SCAN-F', center, True, False, True),
        ]:
            qc = QuantumCircuit(3, name=label)
            if not basis_prep:
                qc.h(0); qc.h(1)
            qc.cx(0, 1)
            qc.rz(angle, 1 if on_target else 0)
            # An unrelated spectator operation is not on either active wire.
            qc.x(2)
            qc.cx(0, 1)
            if analyzer:
                qc.sdg(1); qc.h(1)
            circuits[label] = qc
        return {name: circuit.copy() for name, circuit in circuits.items()}


def exact_probabilities(circuit: QuantumCircuit) -> dict[str, float]:
    """Exact zero-input, computational-basis probabilities, NOT full equivalence."""
    validate_circuit(circuit)
    return {str(k): float(v) for k, v in Statevector.from_instruction(circuit).probabilities_dict().items()}


def sample_counts(circuit: QuantumCircuit, shots=1024, seed=2026) -> dict[str, int]:
    """Ideal local sampling; no physical device, noise model, or network call."""
    validate_circuit(circuit)
    if not isinstance(shots, int) or not 1 <= shots <= 65536:
        raise ValueError('shots must be an integer in 1..65536')
    measured = circuit.copy()
    measured.measure_all()
    simulator = BasicSimulator()
    native = transpile(measured, simulator, seed_transpiler=int(seed))
    return {str(k): int(v) for k, v in simulator.run(
        native, shots=shots, seed_simulator=int(seed)).result().get_counts().items()}


def total_variation(left, right) -> float:
    """TV distance between normalized distributions (not raw counts)."""
    if any(not math.isfinite(float(v)) or v < 0 for v in list(left.values()) + list(right.values())):
        raise ValueError('Probabilities must be finite and nonnegative')
    if not np.isclose(sum(left.values()), 1) or not np.isclose(sum(right.values()), 1):
        raise ValueError('Normalize counts before calling total_variation')
    return float(0.5 * sum(abs(left.get(k, 0) - right.get(k, 0)) for k in left.keys() | right.keys()))


def circuit_digest(circuit: QuantumCircuit) -> str:
    """Byte-level QPY artifact identifier, not a semantic-equivalence test."""
    stream = io.BytesIO()
    qpy.dump(circuit, stream)
    return hashlib.sha256(stream.getvalue()).hexdigest()
