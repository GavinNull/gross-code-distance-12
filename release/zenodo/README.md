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
For the DRAT proofs (section 3, `certificates/proofs/`): git, make and a C/C++ compiler;
`sh code/proofs/build_tools.sh` downloads CaDiCaL, drat-trim and cake_lpr from their official repositories at pinned
commits and builds them into `tools/` (or set `CADICAL`, `DRAT_TRIM`, `CAKE_LPR` to existing binaries).

```sh
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt
#   (or: python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt)
sh code/proofs/build_tools.sh                    # optional: proof tools (run_full.sh calls it when needed)
PYTHON=.venv/bin/python sh run_quick.sh          # about 9 CPU minutes (5 without the proof tools)
PYTHON=.venv/bin/python P=4 sh run_full.sh       # about 16 CPU hours; NO_PROOFS=1: about 4 CPU hours
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
* `weight11_p8_colour_symmetric_944.json.gz` (SM S10, "At P = 8 all 944 legal deterministic circuits … each has a
  weight-11 undetected error at R = 1 in the Z basis"): one fault set per circuit of
  `data/circuits/p8_colour_symmetric_944.json.gz` (circuit name `p8:k`).

### `data/circuits/encoding_completeness_sample.json.gz`
Legal deterministic colour-symmetric circuits at P = 17, 12 (pipelined) and 20 (common frame), drawn independently of
the SAT encodings (seeds 1..25 each); full specification plus the CNOT time of every item. See
`code/sat/completeness_sample.py`.

### `data/circuits/p8_colour_symmetric_944.json.gz`
The 944 legal deterministic colour-symmetric period-8 circuits with orders in the class of Fig. 12, each as the
(variant, start) of the six (type, colour) classes; expansion rule and checks in `code/p8_family.py`.

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
| `order_class_uniqueness/*` | uniqueness of the order class: 24 translation-coset colourings × 2 residual types, each UNSAT after blocking the translates of Fig. 12; every nogood comes from a verified weight-≤10 extended logical. The 3859 witnesses (and the 10 blocked Fig. 12 translates) are in `order_class_uniqueness/witnesses.json.gz`, checked by `code/check_uniqueness_witnesses.py` |
| `fig12_retimings/*` | Table S3 (retimings that keep the Fig. 12 orders; orders pinned with `--pin-fig12`): `primary_P38_common_frame` = "24-translation symmetric, common frame, any P" (in the common frame only the relative order of the CNOTs on each data qubit enters legality, determinism and the frame model, and at P = 38 every strict total order of the 36 class CNOTs is realisable, so P = 38 covers every P); `primary_P08..P12_pipelined` and `second_P08..P12_sym24` = "24-translation symmetric, pipelined, P = 8, …, 12" (both encodings, also for P = 12); `second_P09_subgroup_*` = the ten subgroups of the P = 9 row (orders 12: ⟨(1,2)⟩, ⟨(1,5)⟩, ⟨(0,3),(2,1)⟩; 6: ⟨(2,1)⟩, ⟨(2,4)⟩, ⟨(4,5)⟩; 8: ⟨(0,3),(3,0)⟩; 4: ⟨(0,3),(6,0)⟩, ⟨(3,3)⟩; 3: ⟨(4,2)⟩); `second_P10_subgroup_{1_2,0_3__3_0,2_4}` = the P = 10 row (orders 12, 8, 6); `primary_P16_common_frame_nosym` = "no symmetry, common frame, P ≤ 16" (a common-frame circuit with period P < 16 is also one with period 16). Generated with the encoders of `code/sat/` |
| `fig12_retimings_len2only/*` | Table S3, **proven direction** | the certificates for the theorem-level statement of Table S3: the same 25 rows (same encoders, Fig. 12 orders pinned, same families and subgroups as `fig12_retimings/`), but the CEGAR frame model uses only the 360 weight-11 logicals per basis of the form "ten data columns + one residual of length 2" (the last two CNOT targets of its check), for which the implication "frame-model lift ⇒ weight-11 undetected error of the circuit" is the one proven in SM S9. Every nogood therefore comes from a proven obstruction, and UNSAT of all 25 rows means each obstruction of Table S3 rests only on the proven direction. Generated by `code/sat/len2only.py` (a wrapper that only filters the logical records given to the shipped CEGAR drivers); the CEGAR iteration counts equal those of an independent run with a separately written filter. 25/25 UNSAT; DRAT proofs verified by drat-trim and LRAT cores by cake_lpr (`certificates/proofs/`). The unrestricted `fig12_retimings/*` sets are kept for comparison |
| `frame_model_samples/*.json.gz` | "in 991 sampled cases … every lift asserted by the frame model was confirmed on the exact DEM, and in 99 sampled cases every violated clause corresponded to an exact lift": every sampled case (circuit times, logical, exact lift round), produced by `code/sat/soundness.py` (144 + 847 model claims, 87 + 12 clauses) |

**Encoders.** `code/sat/` contains the two encodings (`enc_primary.py`, `enc_second.py`), the bulk frame model
(`frame.py`) and the CEGAR drivers; `code/sat/regenerate.py` reruns a CEGAR loop and compares the resulting clause
set with the shipped certificate. Every certificate tried is reproduced **byte-identically** (same clause sequence,
same variable numbering; only the DIMACS comment header differs): primary P = 8, 9, 12 pipelined and P = 20 common
frame; second encoding P = 8, 9, 10, subgroup ⟨(1,2)⟩ at P = 9, the window instance X0 at P = 24, and the Table S3
instances (which were generated by these encoders).

The CEGAR loops were rerun to regenerate these clause sets; their iteration counts equal those of the original runs
(e.g. 813 for `P17_pipelined`, primary encoding; 527 for `P17_pipelined`, second encoding; 165 for
`P11_subgroup_1_2`). Re-solve results as stated in SM S10: `P12_pipelined` and `P20_common_frame` (primary encoding)
are UNSAT for all three solvers, `P17_pipelined` for CaDiCaL and Glucose (MiniSat exhausts its conflict budget); every
certificate is UNSAT for CaDiCaL without a budget.


### Which solver proved each certificate

UNSAT = proved unsatisfiable from scratch by that solver; budget = Glucose (≤ 300 000 – 5 000 000 conflicts) or MiniSat (≤ 200 000 – 2 000 000 conflicts) stopped at its conflict budget without an answer. No solver ever returned SAT. CaDiCaL was run without a budget and proves every instance.

| certificate | clauses | UNSAT by | budget exhausted |
|---|---|---|---|
| `fig12_retimings/primary_P08_pipelined` | 26402 | CaDiCaL, Glucose, MiniSat | — |
| `fig12_retimings/primary_P09_pipelined` | 32577 | CaDiCaL, Glucose, MiniSat | — |
| `fig12_retimings/primary_P10_pipelined` | 40665 | CaDiCaL, Glucose, MiniSat | — |
| `fig12_retimings/primary_P11_pipelined` | 51221 | CaDiCaL, Glucose, MiniSat | — |
| `fig12_retimings/primary_P12_pipelined` | 59985 | CaDiCaL, Glucose, MiniSat | — |
| `fig12_retimings/primary_P16_common_frame_nosym` | 654106 | CaDiCaL | Glucose, MiniSat |
| `fig12_retimings/primary_P38_common_frame` | 113566 | CaDiCaL, Glucose | MiniSat |
| `fig12_retimings/second_P08_sym24` | 30016 | CaDiCaL, Glucose, MiniSat | — |
| `fig12_retimings/second_P09_subgroup_0_3__2_1` | 53662 | CaDiCaL, Glucose, MiniSat | — |
| `fig12_retimings/second_P09_subgroup_0_3__3_0` | 73226 | CaDiCaL, Glucose, MiniSat | — |
| `fig12_retimings/second_P09_subgroup_0_3__6_0` | 134900 | CaDiCaL, Glucose, MiniSat | — |
| `fig12_retimings/second_P09_subgroup_1_2` | 48598 | CaDiCaL, Glucose, MiniSat | — |
| `fig12_retimings/second_P09_subgroup_1_5` | 48598 | CaDiCaL, Glucose, MiniSat | — |
| `fig12_retimings/second_P09_subgroup_2_1` | 91446 | CaDiCaL, Glucose, MiniSat | — |
| `fig12_retimings/second_P09_subgroup_2_4` | 95082 | CaDiCaL, Glucose, MiniSat | — |
| `fig12_retimings/second_P09_subgroup_3_3` | 135734 | CaDiCaL, Glucose, MiniSat | — |
| `fig12_retimings/second_P09_subgroup_4_2` | 166226 | CaDiCaL, Glucose, MiniSat | — |
| `fig12_retimings/second_P09_subgroup_4_5` | 89090 | CaDiCaL, Glucose, MiniSat | — |
| `fig12_retimings/second_P09_sym24` | 33976 | CaDiCaL, Glucose, MiniSat | — |
| `fig12_retimings/second_P10_subgroup_0_3__3_0` | 91799 | CaDiCaL, Glucose, MiniSat | — |
| `fig12_retimings/second_P10_subgroup_1_2` | 65192 | CaDiCaL, Glucose, MiniSat | — |
| `fig12_retimings/second_P10_subgroup_2_4` | 122562 | CaDiCaL, Glucose, MiniSat | — |
| `fig12_retimings/second_P10_sym24` | 38505 | CaDiCaL, Glucose, MiniSat | — |
| `fig12_retimings/second_P11_sym24` | 45582 | CaDiCaL, Glucose, MiniSat | — |
| `fig12_retimings/second_P12_sym24` | 51171 | CaDiCaL, Glucose, MiniSat | — |
| `less_symmetry/P08_subgroup_0_3` | 218726 | CaDiCaL, Glucose | MiniSat |
| `less_symmetry/P08_subgroup_1_2` | 51248 | CaDiCaL, Glucose, MiniSat | — |
| `less_symmetry/P08_subgroup_4_2` | 162810 | CaDiCaL, Glucose, MiniSat | — |
| `less_symmetry/P08_subgroup_6_0` | 234182 | CaDiCaL, Glucose, MiniSat | — |
| `less_symmetry/P08_subgroup_6_3` | 218294 | CaDiCaL | Glucose, MiniSat |
| `less_symmetry/P09_subgroup_1_2` | 65732 | CaDiCaL, Glucose, MiniSat | — |
| `less_symmetry/P10_subgroup_1_2` | 96996 | CaDiCaL | Glucose, MiniSat |
| `less_symmetry/P11_subgroup_1_2` | 133180 | CaDiCaL | Glucose, MiniSat |
| `min_period_primary_encoding/P08_pipelined` | 26948 | CaDiCaL, Glucose, MiniSat | — |
| `min_period_primary_encoding/P09_pipelined` | 36063 | CaDiCaL, Glucose, MiniSat | — |
| `min_period_primary_encoding/P10_pipelined` | 45936 | CaDiCaL, Glucose, MiniSat | — |
| `min_period_primary_encoding/P11_pipelined` | 58344 | CaDiCaL, Glucose | MiniSat |
| `min_period_primary_encoding/P12_pipelined` | 69631 | CaDiCaL, Glucose, MiniSat | — |
| `min_period_primary_encoding/P13_pipelined` | 83571 | CaDiCaL | Glucose, MiniSat |
| `min_period_primary_encoding/P14_pipelined` | 99087 | CaDiCaL | Glucose, MiniSat |
| `min_period_primary_encoding/P15_pipelined` | 114844 | CaDiCaL | Glucose, MiniSat |
| `min_period_primary_encoding/P16_pipelined` | 131538 | CaDiCaL | Glucose, MiniSat |
| `min_period_primary_encoding/P17_pipelined` | 148627 | CaDiCaL, Glucose | MiniSat |
| `min_period_primary_encoding/P20_common_frame` | 42775 | CaDiCaL, Glucose, MiniSat | — |
| `min_period_second_encoding/P08_pipelined` | 31699 | CaDiCaL, Glucose, MiniSat | — |
| `min_period_second_encoding/P09_pipelined` | 38292 | CaDiCaL, Glucose, MiniSat | — |
| `min_period_second_encoding/P10_pipelined` | 44910 | CaDiCaL, Glucose, MiniSat | — |
| `min_period_second_encoding/P11_pipelined` | 53067 | CaDiCaL, Glucose, MiniSat | — |
| `min_period_second_encoding/P12_pipelined` | 60717 | CaDiCaL, Glucose, MiniSat | — |
| `min_period_second_encoding/P13_pipelined` | 68851 | CaDiCaL, Glucose | MiniSat |
| `min_period_second_encoding/P14_pipelined` | 76446 | CaDiCaL | Glucose, MiniSat |
| `min_period_second_encoding/P15_pipelined` | 84753 | CaDiCaL | Glucose, MiniSat |
| `min_period_second_encoding/P16_pipelined` | 93354 | CaDiCaL | Glucose, MiniSat |
| `min_period_second_encoding/P17_pipelined` | 101587 | CaDiCaL | Glucose, MiniSat |
| `window_explanation/P24_window14_X0` | 142974 | CaDiCaL | Glucose, MiniSat |
| `window_explanation/P24_window14_Z2` | 144788 | CaDiCaL | Glucose, MiniSat |
| `order_class_uniqueness/*` (all 48) | 14 006 – 30 210 | CaDiCaL, Glucose, MiniSat | — |

Meaning of UNSAT for the period families: every legal deterministic circuit of the family has a weight-11 undetected
error for sufficiently many rounds (bulk Pauli-frame model, SM S9–S10); it is not a statement at fixed small `R`.

### `certificates/proofs/` — DRAT proofs checked with drat-trim

Every infeasibility claim that rests on a SAT/CP computation is accompanied by a DRAT proof checked with drat-trim;
in addition, drat-trim's LRAT output (the core of the proof) was checked with cake_lpr, a proof checker verified in
CakeML. "Accompanied by a DRAT proof" means precisely: (i) the clause set is shipped (`certificates/*/*.cnf.gz`) or,
for the Lemma 2 batches, regenerated deterministically by the shipped encoder with its sha256 recorded; (ii) the DRAT
proof is shipped if it is at most 100 MB (`drat/*.drat.xz`, 115 proofs); otherwise its sha256 and size are recorded
and the shipped scripts regenerate it with the pinned CaDiCaL build (`check_proofs.py --regenerate`,
`run_lift_certs.py --compare`; on the reference machine the regenerated proofs were byte-identical for the 3 large
certificate proofs and the 4 lift batches tried; a different build may produce a different proof, which is then
checked anew); (iii) the drat-trim and cake_lpr output of every check is shipped (`logs/`, including
`logs/lift_circuit_{A,B,C}_logs.txt.gz` for all 984 lift batches). cake_lpr is judged by its output line
`s VERIFIED UNSAT`, never by its exit status (it exits with 0 also on failure); when it is not installed the records
say `"cake_lpr": {"verdict": "not run"}` and the scripts print SKIP. Tools (`TOOLS.txt`): CaDiCaL 3.0.1 (commit `c607304`), drat-trim (commit `2e3b2dc`), cake_lpr (commit `a36874a`,
ARMv8 build). The pipeline (`code/proofs/certify.py`): CaDiCaL solves the plain DIMACS file and writes a binary DRAT
proof; drat-trim checks it (backward checking, default options) and writes the LRAT core; cake_lpr checks the LRAT
core. Sanity tests of the pipeline: a proof truncated to half its lemmas, and the full proof against a CNF with the
CEGAR nogoods removed (satisfiable), are both rejected by drat-trim.

**(a) The 129 = 104 + 25 unsatisfiable instances of `certificates/` (SM S9, S10)**, in two batches:
(a1) the 104 instances of the table above (`fig12_retimings/`, `less_symmetry/`, `min_period_*`, `order_class_uniqueness/`,
`window_explanation/`), which certify the optimality, uniqueness and explanation statements of SM S10 and the
unrestricted Table S3 runs; (a2) the 25 instances of `fig12_retimings_len2only/`, which certify Table S3 in the proven
direction (frame model restricted to the "ten data + one length-2 residual" logicals; see the table above).
`certificates_proofs.jsonl`: one record per CNF (sha256 of the CNF, of the DRAT proof and of the LRAT core, sizes,
verdicts, CPU seconds). Result: **129/129 UNSAT, 129/129 DRAT proofs `s VERIFIED` by drat-trim, 129/129 LRAT cores
`s VERIFIED UNSAT` by cake_lpr; no timeouts** (limit 7200 s per step). Total 3.2 CPU h; DRAT proofs 6.6 GB in total
(the 25 `fig12_retimings_len2only` instances: 0.5 CPU h, 0.9 GB, largest `primary_P16_common_frame_nosym`, 619 781
clauses, 640 MB, drat-trim 669 s, cake_lpr 65 s). The 115 proofs up to 100 MB are shipped in `drat/*.drat.xz` (xz;
1056 MB uncompressed, 256 MB compressed); for the 14 larger ones only the sha256 is shipped, `code/proofs/check_proofs.py --regenerate unshipped`
regenerates and checks them. The largest:

| certificate | clauses | DRAT | CaDiCaL | drat-trim | cake_lpr |
|---|---|---|---|---|---|
| `less_symmetry/P11_subgroup_1_2` | 133180 | 1569 MB | 1881 s | 2622 s | 350 s |
| `min_period_primary_encoding/P17_pipelined` | 148627 | 508 MB | 372 s | 418 s | 98 s |
| `min_period_primary_encoding/P16_pipelined` | 131538 | 426 MB | 279 s | 272 s | 60 s |
| `less_symmetry/P08_subgroup_6_3` | 218294 | 395 MB | 169 s | 303 s | 47 s |
| `less_symmetry/P08_subgroup_6_0` | 234182 | 384 MB | 134 s | 199 s | 36 s |
| `min_period_primary_encoding/P15_pipelined` | 114844 | 314 MB | 212 s | 211 s | 53 s |
| `fig12_retimings_len2only/primary_P16_common_frame_nosym` | 619781 | 640 MB | 769 s | 669 s | 65 s |
| `fig12_retimings/primary_P16_common_frame_nosym` | 654106 | 287 MB | 94 s | 57 s | 9 s |
| `less_symmetry/P10_subgroup_1_2` | 96996 | 252 MB | 158 s | 206 s | 38 s |
| `min_period_primary_encoding/P14_pipelined` | 99087 | 227 MB | 138 s | 140 s | 34 s |
| `min_period_primary_encoding/P13_pipelined` | 83571 | 151 MB | 82 s | 89 s | 24 s |
| `less_symmetry/P08_subgroup_0_3` | 218726 | 134 MB | 26 s | 17 s | 4 s |
| `less_symmetry/P08_subgroup_4_2` | 162810 | 119 MB | 12 s | 7 s | 2 s |
| `window_explanation/P24_window14_Z2` | 144788 | 108 MB | 58 s | 68 s | 10 s |

`logs/` holds the drat-trim and cake_lpr output of every check. As before, a proof certifies only that the clause set
is unsatisfiable; that the clauses encode the stated family (and that the CEGAR nogoods are sound) is argued in SM S10
and checked by the scripts of section 4.

**(b) Lemma 2: the lift instances.** A lift instance (circuit, basis, R, one of the 4224 weight-11 logicals) is
the CP-SAT model of SM S6 written as CNF (`code/proofs/lift_cnf.py`): one variable per DEM mechanism of the eleven
image groups, exactly one per group (at-least-one clause; pairwise or ladder at-most-one), and for every detector
touched by these mechanisms the XOR of its mechanisms = 0 (Tseitin chain, pieces of at most 5 literals). The
instances of one (circuit, basis, R) are combined into batch CNFs as a disjunction: selector `t_i` per logical,
clause `(t_1 ∨ … ∨ t_m)`, every clause of instance `i` extended by `¬t_i` (disjoint variables), so a batch is UNSAT
iff none of its instances lifts. Batch `s` of `K = max(1, ⌈R/2⌉)` holds the logicals `i ≡ s (mod K)`. Coverage:

| circuit | R | bases | batch CNFs | instances | result | CPU (solve + both checks) |
|---|---|---|---|---|---|---|
| A (Theorem 1) | 1–32 | Z, X | 544 | 270 336 = 4224 × 32 × 2 | all UNSAT, DRAT verified by drat-trim, LRAT core verified by cake_lpr | 4.8 h |
| B | 1–24 | Z, X | 312 | 202 752 = 4224 × 24 × 2 | all UNSAT, drat-trim and cake_lpr verified | 2.2 h |
| C | 1–14, 16 | Z, X | 128 | 126 720 = 4224 × 15 × 2 | all UNSAT, drat-trim and cake_lpr verified | 0.95 h |

The batch CNFs (up to 2.65 M clauses) and their proofs (up to 87 MB each, 41 GB for circuit A) are not shipped:
`lift_circuit_{A,B,C}.jsonl` records for every batch the sha256 of the CNF, of the DRAT proof and of the LRAT core,
the verdicts and times, and the DEM statistics; `code/proofs/run_lift_certs.py … --compare` regenerates the CNFs
(deterministic: their sha256 must equal the records), refutes and checks them again. Positive control of the
encoding (`code/proofs/lift_control.py fig12 Z 1`, `… X 1`, `lift_control.txt`): for Fig. 12 at R = 1, all 4224
single-logical CNFs are SAT and each CaDiCaL model decodes to one mechanism per group with all detector sums zero.
The input of the CNF (the DEM groups) is built by the same code as for CP-SAT and passes the same checks (template
identity, image set = extended code).

**(c) Not certified by DRAT: `d_ext = 11` and the completeness of the 4224 list.** These rest on the two exhaustive
depth-first searches of SM S4 (`code/dext/`). A CNF encoding of "`H x = 0`, `L x ≠ 0`, `|x| ≤ w`" (XOR rows by
Tseitin chains, sequential counter) is out of reach for CDCL: CaDiCaL needs 5 s, 39 s and 182 s for `w = 3, 4, 5`
and does not finish `w = 6` in 10 minutes (a reformulation through the data-qubit image `e = M x` with the weight-6
checks of the code: 21 s, 127 s, > 600 s); extrapolated, `w = 10` would take of the order of 10^6 CPU seconds, i.e.
far beyond what a DRAT proof could document. CP-SAT does not finish `w = 5` in 10 minutes either.

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
| `code/proofs/check_proofs.py` | SM S10 | drat-trim check of every shipped DRAT proof against its CNF (sha256 of both compared); `--regenerate unshipped`: the 14 proofs over 100 MB are regenerated with CaDiCaL and checked with drat-trim and cake_lpr |
| `code/proofs/run_lift_certs.py A 1-32 OUT --compare certificates/proofs/lift_circuit_A.jsonl` | Lemma 2, SM S6 | the lift batch CNFs (all 4224 logicals, both bases, every R) are regenerated (sha256 = record), refuted by CaDiCaL with a DRAT proof, checked by drat-trim and (LRAT core) by cake_lpr; same for B (`1-24`) and C (`1-14,16`) |
| `code/proofs/lift_control.py fig12 Z 1` | Lemma 2 positive control | all 4224 single-logical lift CNFs of Fig. 12 at R = 1 are SAT, each model decodes to a valid lift |
| `code/proofs/build_tools.sh` | — | downloads (official repositories, pinned commits) and builds CaDiCaL, drat-trim, cake_lpr into `tools/` |
| `code/class_table.py A` | Table I, S1, S2 | prints the specification grouped by (type, colour) class |
| `code/compare_lifts.py` | Lemma 2, SM S6, S11 ("two independent implementations") | runs three lift implementations — CP-SAT (`gross12/ext.py`), frontier dynamic programming and solver-free meet-in-the-middle (`code/lift_independent.py`, own DEM parsing and own extended-code construction) — on circuit A (`R = 1..3`) and Fig. 12 (`R = 1`), both bases, and checks that they return the same set of lifting logicals; `lift_independent.py --method dp --R 1-32` runs the second implementation alone on any range |
| `code/sat/len2only.py NAME` | SM S9 Table S3 (proven direction) | reruns the CEGAR of a Table S3 row with the frame model restricted to the "ten data + one length-2 residual" logicals and compares the clause set with `certificates/fig12_retimings_len2only/NAME.cnf.gz` (byte-identical) |
| `code/sat/regenerate.py` | SM S10, S9 Table S3 | reruns a CEGAR loop with the shipped encoders and compares with the certificate (byte-identical clause sequence) |
| `code/sat/soundness.py 17 0 60 15`, `… 17 0 4 4 all` | SM S10 "soundness of the clauses" | 144 + 847 = 991 model claims and 87 + 12 = 99 excluding clauses, each confirmed by the exact lift |
| `code/p8_family.py enumerate / encoding / check` | SM S10 "completeness of the family encoding", "at P = 8 all 944 …" | independent backtracking enumeration = the 944 listed circuits; the primary SAT encoding at P = 8 without nogoods has exactly these 944 models; all legal, deterministic, extended code = Fig. 12's (their weight-11 witnesses: `verify_witnesses.py`) |
| `code/sat/completeness_sample.py check` | SM S10 "75 independently sampled legal deterministic circuits at P = 12, 17 (pipelined) and 20 (common frame) are all models" | the circuits of `data/circuits/encoding_completeness_sample.json.gz` (drawn by an own CP-SAT sampler, `… sample`) are legal, deterministic, and models of the primary encoding |
| `code/check_uniqueness_witnesses.py` | SM S10 "uniqueness of the order class" | all 3859 weight-≤10 witnesses behind the 48 uniqueness CNFs are genuine extended logicals of their assignment; the blocked survivors are Fig. 12 translates |

Lemma 1 (reduction) and the deletion/splitting arguments of Lemma 3 are pen-and-paper (SM S5, S7); the scripts
check their premises on the actual circuits. The weight-11 lift computation uses CP-SAT with one worker and a fixed
seed; any SAT/infeasible answer is exact.

---------------------------------------------------------------------------------------------------------------------

## 5. Expected output and runtimes

Runtimes are single-core CPU times on an Apple M-series laptop (stim 1.16.0, ortools 9.15).

| command | expected result | CPU time |
|---|---|---|
| `sh run_quick.sh` | `ALL PASS` (see `expected_output_quick.txt`) | 9 min (4 min without the proof tools) |
| `code/check_circuits.py A B C fig12` | 45 `PASS` lines | 0.5 min |
| `code/lift.py --circuit A --basis Z X --R 1-3` | 6 × `PASS … 0/4224 … lift (expected 0)` | 15 s |
| `code/lift.py --circuit A --basis Z X --R 1-32` | 64 × `PASS … 0/4224` | ≈ 1 h |
| `code/lift.py --circuit fig12 --basis Z X --R 1` | 2 × `PASS … 4224/4224` | 6 s |
| `code/premises.py --circuit A` | `G = 52`, insertion at `x ∈ [4, 18R]`, `R' ≤ 32` | 40 s |
| `code/inject_upper_bound.py A B C` | 26 `PASS` lines | 1 min |
| `code/verify_witnesses.py` | 55 `PASS` lines (25 344 + 48 + 944 fault sets) | 22 min |
| `code/check_certificates.py` | 129 `PASS` lines (one per certificate), all `UNSAT` | 55 min (one instance, `less_symmetry/P11_subgroup_1_2`, takes 16 min) |
| `code/proofs/check_proofs.py` | 115 `PASS … drat-trim VERIFIED` lines, 14 `skip` (not shipped) | 10 min |
| `code/proofs/check_proofs.py --regenerate unshipped` | 14 `PASS` lines | 2.9 h (`less_symmetry/P11_subgroup_1_2`: 1.3 h) |
| `code/proofs/run_lift_certs.py A 1-32 …` / `B 1-24` / `C 1-14,16` | one `PASS` line per batch (544 / 312 / 128), `UNSAT`, `drat-trim VERIFIED`, `cake_lpr VERIFIED UNSAT`, `cnf sha256 = record` | 6 h / 2.6 h / 1.2 h (incl. CNF generation) |
| `code/proofs/lift_control.py fig12 Z 1` | `PASS … 4224/4224 single instances SAT` | 1 min |
| `code/compare_lifts.py` | 16 `PASS` lines, identical sets for CP-SAT, DP and MITM | 4 min (MITM at `R = 3`: 3 min) |
| `code/sat/regenerate.py primary 12` | `PASS IDENTICAL …` | 30 s |
| `code/sat/len2only.py NAME` (25 names: `… list`) | `PASS  IDENTICAL` vs `fig12_retimings_len2only/NAME.cnf.gz` | 25 rows: 12 min (`primary_P16_common_frame_nosym`: 10 min) |
| `code/sat/soundness.py 17 0 60 15` / `17 0 4 4 all` | `PASS … 144/144 … 87/87` / `PASS … 847/847 … 12/12` | 4 min / 2 min |
| `code/p8_family.py enumerate`, `encoding`, `check` | one `PASS` each | 10 s, 30 s, 1 min |
| `code/check_uniqueness_witnesses.py` | 48 `PASS` lines, 3859 witnesses | 6 s |
| `code/sat/completeness_sample.py check` | 3 `PASS` lines: 25/25 legal, deterministic and models at P = 17, 20 (common frame), 12 | 7.5 min (`sample`: 10 min) |
| `code/dext/run_dext.sh w10` | `PASS d_ext >= 11` for both bases (≈ 2.0 × 10^10 nodes per basis, 0 solutions) | ≈ 20 min |
| `code/dext/run_dext.sh w11` | `PASS weight-11 list` for both bases: 254 (Z) and 257 (X) raw solutions, 6 174 513 371 and 5 819 348 553 nodes, 4224 logicals each | ≈ 1 h |

---------------------------------------------------------------------------------------------------------------------

## 6. Scope

All statements are for the template of `code/gross12/schedule.py` (single ancilla per check, CNOT gates, memory
experiments) and SD6 noise with independent single-operation faults counted as detector-error-model mechanisms.
Lower bounds hold for every sub-model of SD6. The optimality statements are restricted to the families described in
the paper (colour-symmetric schedules with orders in the class of Fig. 12, and the listed subgroups); they are bulk
statements ("for sufficiently many rounds").
