# Data and verification code: a single-ancilla syndrome circuit with circuit distance 12 for the gross code

This data set accompanies the paper *A single-ancilla syndrome circuit with circuit distance 12 for the gross code*
([arXiv identifier — to be added]). It contains the circuit specifications, the extended codes and the complete
lists of 4224 weight-11 extended logicals per memory basis, explicit witnesses for every upper bound, the clause sets
of the unsatisfiable SAT instances behind the optimality statements, and standalone scripts that reproduce the
computer-checked steps of the proof of Theorem 1 (`d_circ = 12` for circuit A, both memory bases, every number of
rounds) and of Corollary 1 (`d_circ = 11` for Fig. 12 of Strikis, Browne and Beverland (SBB), arXiv:2603.05481).

Licence: data CC BY 4.0, code MIT (see `LICENSE`).
Citation: see `CITATION.cff` (placeholder).

---------------------------------------------------------------------------------------------------------------------

## 1. Quick start

Requirements: Python 3.12, a C compiler (`cc`, only for the exhaustive searches of `code/dext/`), ~2 GB RAM.

```sh
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt
#   (or: python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt)
PYTHON=.venv/bin/python sh run_quick.sh          # about 5 CPU minutes
PYTHON=.venv/bin/python P=4 sh run_full.sh       # about 4 CPU hours (about 1.2 hours with P = 4)
```

All scripts are run from the package root. Every check prints a line starting with `PASS` or `FAIL`; the drivers end
with `ALL PASS` or `SOME CHECKS FAILED` (exit code 1). `expected_output_quick.txt` is the output of `run_quick.sh`
on the reference machine.

Pinned versions (`requirements.txt`, also `pyproject.toml`): stim 1.16.0, numpy 2.2.6, ortools 9.15.6755 (CP-SAT),
python-sat 1.9.dev15 (CaDiCaL 1.5.3, Glucose 4, MiniSat 2.2), with their dependencies pinned.

---------------------------------------------------------------------------------------------------------------------

## 2. Conventions

* **Code.** Gross code `[[144,12,12]]` of arXiv:2308.07915: `l = 12`, `m = 6`, `A = x^3 + y + y^2`,
  `B = y^3 + x + x^2`, `HX = [A | B]`, `HZ = [B^T | A^T]`. Qubit and check index `6a + b` for the monomial `x^a y^b`;
  data qubits `0..71` (left block) and `72..143` (right block). Term labels `A1 = x^3, A2 = y, A3 = y^2,
  B1 = y^3, B2 = x, B3 = x^2`. The X check at `(x, y)` acts on left qubit `(x, y) + A_k` and right qubit
  `(x, y) + B_k`; the Z check at `(x, y)` on left qubit `(x, y) - B_k` and right qubit `(x, y) - A_k`. Colour of a
  check: `(x + y) mod 3`.
* **Memory experiments and template.** See the docstring of `code/gross12/schedule.py` (identical to SM S1 of the
  paper): one ancilla per check (X ancillas `144..215`, Z ancillas `216..287` in row order), reset / six CNOTs /
  measurement per round, `R` rounds, transversal data readout; detectors = first measurement, consecutive
  comparisons, last measurement vs. readout parity, for the checks of the memory basis; observables = the 12 rows of
  `LZ` (Z basis) or `LX` (X basis) from `data/code/gross_code.json`.
* **Noise.** SD6 (`code/gross12/noise.py`): `DEPOLARIZE2` after every CNOT, flip after every reset and before every
  measurement, `DEPOLARIZE1` on every idle qubit in every layer. Faults are counted as distinct detector-error-model
  mechanisms.
* **Basis naming.** Files are labelled by the *memory basis*: the "Z-basis memory" sees X errors, uses `H = HZ`,
  `L = LZ` and the residuals of the X-check CNOT orders; the "X-basis memory" is the mirror image.

---------------------------------------------------------------------------------------------------------------------

## 3. Data dictionary

### `data/code/gross_code.json`
`HX`, `HZ` (72 rows each), `LX`, `LZ` (12 rows each), each row given as the sorted list of columns where it is 1.
`code/gross12/code.py` checks `HX`, `HZ` against the polynomial definition, `k = 12`, and that `LX`, `LZ` are
logical operators with a rank-12 pairing. All lists of logicals refer to these `LX`, `LZ` rows.

### `data/circuits/*.json` — circuit specifications, format `qec-schedule/v1`
```
{"format": "qec-schedule/v1", "name": "...", "period": P,
 "x_checks": [{"prep": s, "meas": m, "cnots": [[data_qubit, step], ... 6 entries]}, ... 72 entries in HX row order],
 "z_checks": [... 72 entries in HZ row order ...]}
```
All steps are in `0..P-1` and are read cyclically from `prep`; the CNOT order of a check is the order of the offsets
`(step - prep) mod P`. A window may cross the period boundary. The full semantics (unrolling to `R` rounds, global
shift, readout) is in `code/gross12/schedule.py`. `python code/class_table.py <name>` prints a file as Table I.

| file | paper | period | statement |
|---|---|---|---|
| `circuit_A.json` | Table I, Fig. 2(a), Theorem 1 | 18, pipelined | `d_circ = 12`, both bases, every `R` |
| `circuit_B.json` | Table S1 | 18, pipelined | `d_circ = 12` (SM S2, S6, S7) |
| `circuit_C.json` | Table S2 | 21, common frame (reset 0, measurement 20) | `d_circ = 12` (SM S2, S6, S7) |
| `fig12.json` | Fig. 12 of SBB, Fig. 2(b), Corollary 1 | 8, pipelined, non-interleaved | `d_circ = 11` |
| `fig12_retiming_{0,1,2,3}.json` | SM S9 ("Retimings with period ≤ 8") | 8 | the 4 conflict-free start assignments up to translation that keep the Fig. 12 orders; retiming 0 is Fig. 12 up to a global time shift; each has weight-11 undetected errors for `R = 1..6` |

### `data/extended_code/extended_code_{Z,X}_memory.json` — extended codes (SM S3, S4)
360 merged columns per basis. Column `j`: `support` (representative data-qubit set: one data qubit, or a residual of
a check order), `kind` (`data` / `residual`), `H` (check rows with odd overlap), `L` (logical rows with odd overlap),
`check_weight` (3, 6 or 9: 144/144/72 columns), `orbit` (one of 15 orbits of the 24 translations),
`fig12_realisations` (every data qubit or `(check, after_cnot, residual)` of Fig. 12 with this column).
Also `translation_group` (the 24 translations `(a, b)`, `a + b = 0 mod 3`, that preserve the Fig. 12 orders) and
`orbits`. Circuits A, B, C have exactly this column set (checked by `code/check_circuits.py`).

### `data/logicals/weight11_logicals_{Z,X}_memory.json` — the 4224 weight-11 extended logicals (SM S4)
`logicals[i].columns`: 11 distinct column indices whose `H` parts sum to zero and whose `L` parts do not;
`logical_flipped`: rows of `L` with odd sum; `orbit`: one of the 176 free orbits under the 24 translations;
`ten_data_plus_one_length2_residual`: true for the 360 logicals of the form "ten data columns + one residual of
length 2" discussed in the Key-idea paragraph. These lists are the input of Lemma 2; `code/dext/` recomputes them.

### `witnesses/`
* `upper_bound_weight12.json` (SM S8): a weight-12 X-type logical (Z basis) and a weight-12 Z-type logical (X basis),
  applied as after-reset flips of the data qubits. Verified by `code/inject_upper_bound.py`.
* `weight11_fig12.json.gz` (Corollary 1 upper bound, SM S9 "Lift structure"): for Fig. 12, each basis, `R = 1, 2, 3`
  and **every** one of the 4224 weight-11 extended logicals, eleven explicit circuit faults that realise it and fire
  no detector (25 344 fault sets).
* `weight11_fig12_retimings.json.gz` (SM S9 "Retimings with period ≤ 8"): for each of the 4 retimings, each basis
  and `R = 1..6`, one weight-11 undetected fault set.

Fault format (`code/gross12/faults.py`): `{"op": index of the noise instruction in the flattened SD6 circuit built by
gross12.ext.noisy_circuit, "tick": layer, "gate": DEPOLARIZE1 / DEPOLARIZE2 / X_ERROR / Z_ERROR, "qubits": targets
of the channel component, "paulis": e.g. ["X12", "Z148"]}`; `logical` indexes the 4224-list of that basis.

### `certificates/` — unsatisfiable instances behind the optimality statements (SM S10)
Each instance: `NAME.cnf.gz` (DIMACS; the header states what it encodes and which clauses are the family encoding
and which are CEGAR nogoods), `NAME.log.json` (description, clause/variable counts, sha256 of the uncompressed CNF,
results and CPU times of a from-scratch re-solve with CaDiCaL 1.5.3, Glucose 4 and MiniSat 2.2 — MiniSat and Glucose
with a conflict budget, `UNKNOWN` = budget exhausted — and, for CEGAR instances, `family_only`: the family encoding
alone is satisfiable), and for CEGAR instances `NAME.varmap.json.gz` (variable id → encoder object).

| directory | paper statement |
|---|---|
| `min_period_primary_encoding/P08..P17_pipelined`, `P20_common_frame` | "pipelined schedules with P = 8, …, 17 and common-frame schedules with P = 20 are unsatisfiable"; minimal periods 18 and 21 (colour-symmetric family, Fig. 12 order class) |
| `min_period_second_encoding/P08..P17_pipelined` | "a second, independent encoding (absolute times, one-sided difference literals) agrees for P = 8, …, 17" |
| `less_symmetry/P08..P11_subgroup_1_2` | "invariance under the order-12 subgroup generated by (1,2) excludes P ≤ 11" |
| `less_symmetry/P08_subgroup_{0_3,6_0,6_3,4_2}` | "any non-trivial subgroup excludes P = 8": these are the four minimal non-trivial subgroups of the 24 colour-preserving translations (orders 2, 2, 2, 3); every non-trivial subgroup contains one of them, so its family is contained in one of these UNSAT families |
| `window_explanation/P24_window14_{X0,Z2}` | "restricting the CNOT window of class X0 or of class Z2 to at most 14 steps is unsatisfiable at P = 24" (explanation only, not used for a bound) |
| `order_class_uniqueness/*` | uniqueness of the order class: 24 translation-coset colourings × 2 residual types, each UNSAT after blocking the translates of Fig. 12; every nogood comes from a verified weight-≤10 extended logical |

The CEGAR loops were rerun to regenerate these clause sets; their iteration counts equal those of the original runs
(e.g. 813 for `P17_pipelined`, primary encoding; 527 for `P17_pipelined`, second encoding; 165 for
`P11_subgroup_1_2`). Re-solve results as stated in SM S10: `P12_pipelined` and `P20_common_frame` (primary encoding)
are UNSAT for all three solvers, `P17_pipelined` for CaDiCaL and Glucose (MiniSat exhausts its conflict budget); every
certificate is UNSAT for CaDiCaL without a budget.

Meaning of UNSAT for the period families: every legal deterministic circuit of the family has a weight-11 undetected
error for sufficiently many rounds (bulk Pauli-frame model, SM S9–S10); it is not a statement at fixed small `R`.

---------------------------------------------------------------------------------------------------------------------

## 4. Scripts and how they map to the paper

| script | paper | what it checks |
|---|---|---|
| `code/check_circuits.py A B C fig12` | SM S2, S3 | legality, determinism (noiseless circuits, `R = 1, 2, 3, 6`), reset/measurement steps, interleaving (X/Z switches per data qubit), CNOT orders in the class `<rev, s12, s56>` of Fig. 12, extended-code column set = Fig. 12's, and for `R = 1..3` the template identity and image set used in Lemma 1 |
| `code/dext/run_dext.sh w10` | SM S4, `d_ext = 11` | exhaustive search: no extended logical of weight ≤ 10 (both bases; 15 orbit cases) |
| `code/dext/run_dext.sh w11` | SM S4, the 4224 list | exhaustive enumeration of weight-11 extended logicals, expanded by the 24 translations, equal to `data/logicals` |
| `code/lift.py --circuit A --R 1-32` | Lemma 2, SM S6 | 0 of 4224 logicals lift, both bases, every `R ≤ 32`; also checks per `R` the template identity and that the DEM image set is the extended code (premises of Lemma 1) |
| `code/lift.py --circuit fig12 --R 1` | Lemma 2 positive control | 4224 of 4224 lift |
| `code/lift.py --circuit B --R 1-24`, `--circuit C --R 1-14,16` | SM S6 | as for A |
| `code/premises.py --circuit A` | Lemma 3, SM S7 | `D = 18`, `dm_max = 17`, `S = 5`, `G = 52`, span ≤ 510 layers, layer-by-layer insertion property, `R' = 32` |
| `code/premises.py --circuit B --slab` | SM S7 (circuit B) | slab premise, `R = 3, 8, 24`: 0 violations |
| `code/premises.py --circuit C --separated` | SM S7 (circuit C) | rounds separated in time, insertion property ⇒ `R' ≤ 13` |
| `code/inject_upper_bound.py A B C` | SM S8 | weight-12 injection, `R = 1, 3, 6, 10`, both bases; omitting any flip is detected |
| `code/verify_witnesses.py` | Corollary 1, SM S9 | every weight-11 fault set fires no detector, flips an observable, consists of 11 distinct mechanisms and realises the listed extended logical |
| `code/check_certificates.py` | SM S10 | sha256 and from-scratch CaDiCaL re-solve: UNSAT for every certificate |
| `code/class_table.py A` | Table I, S1, S2 | prints the specification grouped by (type, colour) class |

Lemma 1 (reduction) and the deletion/splitting arguments of Lemma 3 are pen-and-paper (SM S5, S7); the scripts
check their premises on the actual circuits. The weight-11 lift computation uses CP-SAT with one worker and a fixed
seed; any SAT/infeasible answer is exact.

---------------------------------------------------------------------------------------------------------------------

## 5. Expected output and runtimes

Runtimes are single-core CPU times on an Apple M-series laptop (stim 1.16.0, ortools 9.15).

| command | expected result | CPU time |
|---|---|---|
| `sh run_quick.sh` | `ALL PASS` (see `expected_output_quick.txt`) | 2.5 min |
| `code/check_circuits.py A B C fig12` | 45 `PASS` lines | 0.5 min |
| `code/lift.py --circuit A --basis Z X --R 1-3` | 6 × `PASS … 0/4224 … lift (expected 0)` | 15 s |
| `code/lift.py --circuit A --basis Z X --R 1-32` | 64 × `PASS … 0/4224` | ≈ 1 h |
| `code/lift.py --circuit fig12 --basis Z X --R 1` | 2 × `PASS … 4224/4224` | 6 s |
| `code/premises.py --circuit A` | `G = 52`, insertion at `x ∈ [4, 18R]`, `R' ≤ 32` | 40 s |
| `code/inject_upper_bound.py A B C` | 26 `PASS` lines | 1 min |
| `code/verify_witnesses.py` | 54 `PASS` lines (25 344 + 48 fault sets) | 13 min |
| `code/check_certificates.py` | 79 `PASS` lines (one per certificate), all `UNSAT` | 40 min (one instance, `less_symmetry/P11_subgroup_1_2`, takes 16 min) |
| `code/dext/run_dext.sh w10` | `PASS d_ext >= 11` for both bases (≈ 2.0 × 10^10 nodes per basis, 0 solutions) | ≈ 20 min |
| `code/dext/run_dext.sh w11` | `PASS weight-11 list` for both bases: 254 (Z) and 257 (X) raw solutions, 6 174 513 371 and 5 819 348 553 nodes, 4224 logicals each | ≈ 1 h |

---------------------------------------------------------------------------------------------------------------------

## 6. Scope

All statements are for the template of `code/gross12/schedule.py` (single ancilla per check, CNOT gates, memory
experiments) and SD6 noise with independent single-operation faults counted as detector-error-model mechanisms.
Lower bounds hold for every sub-model of SD6. The optimality statements are restricted to the families described in
the paper (colour-symmetric schedules with orders in the class of Fig. 12, and the listed subgroups); they are bulk
statements ("for sufficiently many rounds").
