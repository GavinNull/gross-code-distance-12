# Data and verification code: interleaving recovers the full circuit distance of the gross and [[90,8,10]] bivariate-bicycle codes

Version 2.0.  This data set accompanies the paper *Interleaving recovers the full circuit distance of the gross and
[[90,8,10]] bivariate-bicycle codes* ([arXiv identifier — to be added]).  It contains the circuit specifications, the
codes, the extended codes and the complete lists of the lightest extended logicals used in the lift computations,
the witnesses of every upper bound, the certificates of every infeasibility claim used in the proofs (VeriPB and DRAT
/ LRAT proofs, or their SHA-256 hashes with the scripts that regenerate them, and the checker logs), the sampling
statistics of the logical-error-rate comparisons, and standalone scripts that reproduce the computer-checked steps of

* **Theorem 1** (main text; SM S3): the period-11 single-ancilla circuit u11 of the gross code `[[144,12,12]]` has
  `d_circ = 12` under SD6 noise, both memory bases, every number of rounds `R`;
* **Theorem 2** (main text; SM S4): the period-11 circuit c11 of `[[90,8,10]]` has `d_circ = 10`, both bases, every
  `R`; the same holds for the non-wrapping period-12 circuit c12 and for the period-16 circuit c16 (and for c13, a
  period-13 variant of c16 that is not discussed in the paper); for every
  assignment of per-check CNOT orders the X-side extended code of `[[90,8,10]]` has a logical of weight `<= 8` (DRAT
  proof), so every non-interleaved circuit has `d_circ <= 8`;
* **Corollary 1** (SM S9, S10): Fig. 12 of Strikis, Browne and Beverland (SBB, arXiv:2603.05481) has `d_circ = 11`,
  and retimings of Fig. 12 that keep its orders cannot reach 12 (Table S5);
* the **direct searches** on the full detector error model without the extended code (SM S5);
* the **certificates** (SM S6, S18);
* the **logical error rates** under SD6 with rescaled idle noise (SM S7) and in a neutral-atom model (SM S8);
* the earlier gross circuits A, B (period 18) and C (period 21) with `d_circ = 12` (SM S11–S16) and the idle-noise
  study of SM S17 (circuits A, B, C are kept as history; the headline circuits are u11 and c11).

Licence: data CC BY 4.0, code MIT (see `LICENSE`).  Citation: see `CITATION.cff` (placeholders until publication).

**Section numbers** follow the current paper: SM S1 notation and noise, S2 proof of Lemma 1, S3 the period-11 gross
circuit, S4 the `[[90,8,10]]` code and its circuits, S5 direct search, S6 certificates, S7 logical error rates, S8
neutral-atom model, S9 Fig. 12 and its retimings, S10 the extended code of Fig. 12 (`d_ext = 11`, 4224 logicals), S11
invariance of the extended code, S12 circuits A, B, C, S13 lift for A, B, C, S14 round reduction for A, B, C, S15 upper
bound for A, B, C, S16 search and optimality, S17 idle noise, S18 verification and data, S19 the morphing end-cycle
code.  Lemma 1 = reduction (images of undetected faults form an extended logical), Lemma 2 = light logicals (weight
`d_ext` and `d_ext + 1`).  Tables: Table I (main text, the two period-11 circuits), Table S1 (c16), S2–S4 (neutral
atoms), S5 (retimings of Fig. 12), S6–S8 (circuits A, B, C), S9–S10 (idle noise).  Descriptions inside a few data
files written for version 1 use older numbers: in `data/circuits/p8_colour_symmetric_944.json.gz` "SM S10" is the
present S16; in the descriptions and comment headers of `certificates/*/` the optimality and Table S3 statements are
the present S16 and Table S5.

**What is new in version 2.0**: the period-11 circuits u11 and c11 (and c12, c13), the u11 extended code and its
complete lists, the extended-lift scripts for every circuit of the template (`code/p11/`), the any-`R` premises, the
injections, the second direct DEM search (`code/p11/direct.py`), the VeriPB certificates of `d_ext` and of the
completeness of every list used (`certificates/veripb/`, `code/veripb/`), the DRAT certificates of every lift instance
of u11 (`R <= 31`), c11 (`R <= 25`), c12, c13, c16 (`R <= 12`) (`certificates/proofs/lift_*.jsonl`,
`code/proofs/ext_lift_certs.py`), the logical-error-rate data and the neutral-atom noise model (`data/ler/`,
`code/ler/`).  Everything of version 1.1 is kept.

---------------------------------------------------------------------------------------------------------------------

## 1. Quick start

Requirements: Python 3.12 and a C compiler (`cc`).  Optional: the proof tools (CaDiCaL 3.0.1, drat-trim, cake_lpr:
`sh code/proofs/build_tools.sh` downloads them from their official repositories at pinned commits and builds them
into `tools/`; needs git, make, a C/C++ compiler), VeriPB 3.0.2 (`sh code/veripb/build_veripb.sh`, needs git and a
Rust toolchain), and the logical-error-rate dependencies (`requirements-ler.txt`: sinter, stimbposd / ldpc, relay-bp).
Tool locations can be given by `CADICAL`, `DRAT_TRIM`, `CAKE_LPR`, `VERIPB`.

```sh
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt
uv pip install --python .venv/bin/python -r requirements-ler.txt      # optional (code/ler/)
#   (or: python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-ler.txt)
sh code/proofs/build_tools.sh                    # optional: CaDiCaL, drat-trim, cake_lpr
sh code/veripb/build_veripb.sh                   # optional: VeriPB 3
PYTHON=.venv/bin/python sh run_quick.sh          # about 13 CPU minutes (with all optional tools)
PYTHON=.venv/bin/python P=4 sh run_full.sh       # see section 6 for the parts and their CPU times
```

All scripts are run from the package root.  Every check prints a line starting with `PASS` or `FAIL` (`SKIP` for a
check whose optional tool is absent); the drivers end with `ALL PASS` or `SOME CHECKS FAILED` (exit code 1).
`expected_output_quick.txt` is the output of `run_quick.sh` on the reference machine (with all optional tools).

Pinned versions (`requirements.txt`, also `pyproject.toml`): stim 1.16.0, numpy 2.2.6, ortools 9.15.6755 (CP-SAT),
python-sat 1.9.dev15 (CaDiCaL 1.5.3, Glucose 4, MiniSat 2.2), with their dependencies pinned; `requirements-ler.txt`:
sinter 1.16.0, stimbposd 0.2.0, ldpc 2.4.1, relay-bp 0.2.2, scipy 1.18.1 and their dependencies.  Proof tools:
`certificates/proofs/TOOLS.txt`.

---------------------------------------------------------------------------------------------------------------------

## 2. Conventions

* **Gross code** `[[144,12,12]]` of arXiv:2308.07915: `l = 12`, `m = 6`, `A = x^3 + y + y^2`, `B = y^3 + x + x^2`,
  `HX = [A | B]`, `HZ = [B^T | A^T]`.  Qubit and check index `6a + b` for the monomial `x^a y^b`; data qubits `0..71`
  (left block) and `72..143` (right block).  Term labels `A1 = x^3, A2 = y, A3 = y^2, B1 = y^3, B2 = x, B3 = x^2`.  The X
  check at `(x, y)` acts on left qubit `(x, y) + A_k` and right qubit `(x, y) + B_k`; the Z check at `(x, y)` on left
  qubit `(x, y) - B_k` and right qubit `(x, y) - A_k`.  Colour of a check: `(x + y) mod 3`.
* **`[[90,8,10]]`** (`code/bb90/bbcode.py`): `l = 15`, `m = 3`, `A = x^9 + y + y^2`, `B = 1 + x^2 + x^7`; index `3a + b`;
  data qubits `0..44` and `45..89`; labels `A1 = x^9, A2 = y, A3 = y^2, B1 = 1, B2 = x^2, B3 = x^7`.  The 45 translations
  are code automorphisms that preserve the labels.
* **Memory experiments and template** (SM S1; docstring of `code/gross12/schedule.py`, written for any CSS code): one
  ancilla per check (X ancillas after the data qubits, then Z ancillas, in row order), per round reset / six CNOTs /
  measurement, `R` rounds, transversal data readout; detectors = first measurement, consecutive comparisons, last
  measurement vs. readout parity, for the checks of the memory basis; observables = the rows of `LZ` (Z basis) or `LX`
  (X basis) of `data/code/*_code.json`.
* **Noise.** SD6 (`code/gross12/noise.py`): `DEPOLARIZE2` after every CNOT, flip after every reset and before every
  measurement, `DEPOLARIZE1` on every idle qubit in every layer.  Faults are counted as distinct detector-error-model
  (DEM) mechanisms.  For the logical error rates: `lam<x>` = SD6 with the idle channel scaled to `x p`
  (`code/ler/noise.py`), and the neutral-atom model `code/ler/na_noise.py`.
* **Basis naming.** Files are labelled by the *memory basis*: the "Z-basis memory" sees X errors, uses `H = HZ`,
  `L = LZ` and the residuals of the X-check CNOT orders; the "X-basis memory" is the mirror image.
* **Extended code** (SM S2, S3): columns = the data qubits and the proper suffixes (residuals) of the check orders of
  the hook type, as pairs `(H s, L s)`, equal pairs merged; column order in the data files: data qubits first, then for
  every check in row order its suffixes of length 5, 4, 3, 2, 1, first occurrence kept.

---------------------------------------------------------------------------------------------------------------------

## 3. Data dictionary

### `data/code/gross_code.json`, `data/code/bb90_code.json`
`HX`, `HZ`, `LX`, `LZ`, each row given as the sorted list of columns where it is 1 (gross: 72 / 72 / 12 / 12 rows;
`[[90,8,10]]`: 45 / 45 / 8 / 8).  `code/gross12/code.py` and `code/bb90/bbcode.py` check `HX`, `HZ` against the
polynomial definition, `k`, and that `LX`, `LZ` are logical operators with a full-rank pairing.  Every list of
logicals refers to these rows.

### `data/circuits/*.json` — circuit specifications, format `qec-schedule/v1`
```
{"format": "qec-schedule/v1", "name": "...", "period": P,
 "x_checks": [{"prep": s, "meas": m, "cnots": [[data_qubit, step], ... 6 entries]}, ... in HX row order],
 "z_checks": [... in HZ row order ...]}
```
All steps are in `0..P-1` and are read cyclically from `prep`; the CNOT order of a check is the order of the offsets
`(step - prep) mod P`; a window may cross the period boundary.  The unrolling to `R` rounds (global shift, readout)
is in `code/gross12/schedule.py`.  Each file below was checked to give, for `R = 1, 2, 3` and both bases, the same
noiseless and SD6 circuits as the template used for the computations of the paper (string equality).

| file | paper | period | statement |
|---|---|---|---|
| `u11.json` | Table I, Fig. 1, Theorem 1, SM S3 | 11, wrapping | `d_circ = 12`, both bases, every `R` |
| `u11_control_p10.json` | SM S3 "Positive controls", S5 | 10, wrapping | same extended code as u11; weight-11 lifts at `R = 1, 2` (432 Z, 576 X): `d_circ <= 11` |
| `u11_control_segmented.json` | SM S3 "Non-segmentability", "Positive controls" | 15 | the u11 orders with an X block and a Z block; every weight-10 / weight-11 extended logical lifts |
| `bb90_c11.json` | Table I, Theorem 2, SM S4 | 11, wrapping | `d_circ = 10`, both bases, every `R` |
| `bb90_c12.json` | SM S4 "Period-11 and period-12 circuits" | 12, non-wrapping | `d_circ = 10` |
| `bb90_c13.json` | not in the paper (a further control) | 13 | c16 without its three CNOT-free steps; same DEM signatures as c16 for `R <= 12`; `d_circ = 10` |
| `bb90_c16.json` | Table S1, SM S4 | 16 | `d_circ = 10` |
| `bb90_u16.json`, `bb90_s16.json` | SM S4 "Lift" (controls) | 16 | `d_circ = 9` (interleaved control) and 8 (non-interleaved, same extended code) |
| `ibm_gross_depth8.json`, `bb90_ibm_depth8.json` | SM S7, S8 (references) | 8 | IBM's depth-8 circuits (arXiv:2308.07915) in the template |
| `fig12.json` | Fig. 12 of SBB, Corollary 1, SM S9 | 8 | `d_circ = 11` |
| `fig12_retiming_{0,1,2,3}.json` | SM S9 "Retimings with period <= 8" | 8 | the 4 conflict-free start assignments up to translation that keep the Fig. 12 orders; each has weight-11 undetected errors for `R = 1..6` |
| `circuit_A.json`, `circuit_B.json`, `circuit_C.json` | Tables S6–S8, SM S12 | 18, 18, 21 | `d_circ = 12`, both bases, every `R` (orders in the class of Fig. 12) |

`python code/class_table.py <name>` prints a gross-code file grouped by (type, colour) class (Tables S6–S8).

### `data/extended_code/` — extended codes
* `u11_extended_code_{Z,X}_memory.json` (SM S3): 360 merged columns per basis, 5 orbits of the 72 translations.
  Column `j`: `support` (representative data-qubit set), `kind` (`data` / `residual`), `H`, `L` (rows with odd overlap),
  `check_weight`, `orbit`, `u11_realisations` (every data qubit or `(check, after_cnot, residual)` of u11 with this
  column).  Also `translation_group` (72 elements) and `orbits`.  The two u11 controls have the same column set.
* `bb90_extended_code_{Z,X}_memory.json` (SM S4): 225 columns per basis, 5 orbits of the 45 translations; the extended
  code of c16, and (as column set) of c11, c12, c13, u16, s16 (checked by `code/p11/check_circuits.py` and
  `code/bb90/check_circuits.py`; the column order of a circuit's own construction may differ, the scripts map by key).
* `extended_code_{Z,X}_memory.json` (SM S10, S11): the extended code of Fig. 12 and of circuits A, B, C (360 columns,
  15 orbits of the 24 colour-preserving translations; `fig12_realisations`).

### `data/logicals/` — complete lists of the lightest extended logicals (the input of the lift)
Each entry: `columns` (indices into the extended-code file of the same basis), `orbit`, `logical_flipped` (rows of `L`
with odd sum).  Completeness of every list is certified by VeriPB (section 3, certificates (a)); the lists were also
obtained by two independent exhaustive enumerations with identical results.

| file | count per basis | orbits | `d_ext` | used by |
|---|---|---|---|---|
| `u11_weight10_logicals_{Z,X}_memory.json` | 144 | 2 free orbits of 72 | 10 | Theorem 1: weight-10 lifts, with and without one zero-image fault |
| `u11_weight11_logicals_{Z,X}_memory.json` | 7344 | 102 | | Theorem 1: weight-11 lifts |
| `bb90_weight8_logicals_{Z,X}_memory.json` | 585 | 13 free orbits of 45 | 8 | Theorem 2 (c11, c12, c13, c16): weight-8 lifts, with and without one zero-image fault |
| `bb90_weight9_logicals_{Z,X}_memory.json` | 16830 | 374 | | Theorem 2: weight-9 lifts |
| `weight11_logicals_{Z,X}_memory.json` | 4224 | 176 free orbits of 24 | 11 | Corollary 1, circuits A, B, C (SM S10, S13); `ten_data_plus_one_length2_residual` marks the 360 logicals of the proven direction of SM S9 |

### `witnesses/`
* `upper_bound_weight12.json`: a weight-12 X-type (Z basis) and a weight-12 Z-type (X basis) data logical of the gross
  code, applied as after-reset flips of the data qubits; verified by `code/p11/inject_upper_bound.py` for u11
  (`R = 1, 2, 3, 6, 10, 31`) and by `code/inject_upper_bound.py` for circuits A, B, C (`R = 1, 2, 3, 6, 10`).
* `bb90_upper_bound_weight10.json`: the weight-10 data logicals of `[[90,8,10]]`; verified for c11, c12, c13
  (`R = 1, 2, 5, 11, 25`) by `code/p11/inject_upper_bound.py` and for c16 (`R = 1, 2, 3, 6, 10, 13`) by
  `code/bb90/inject_upper_bound.py`.
* `weight11_fig12.json.gz`, `weight11_fig12_retimings.json.gz`, `weight11_p8_colour_symmetric_944.json.gz` (SM S9,
  S16): explicit weight-11 undetected fault sets of Fig. 12 (every one of the 4224 logicals, `R = 1, 2, 3`, both
  bases), of its four period-8 retimings (`R = 1..6`) and of the 944 period-8 circuits of
  `data/circuits/p8_colour_symmetric_944.json.gz`.  Fault format (`code/gross12/faults.py`): `{"op": index of the
  noise instruction in the flattened SD6 circuit, "tick", "gate", "qubits", "paulis"}`.

### `data/circuits/encoding_completeness_sample.json.gz`, `data/circuits/p8_colour_symmetric_944.json.gz` (SM S16)
Circuits drawn independently of the SAT encodings, and the 944 period-8 circuits; see `code/sat/completeness_sample.py`
and `code/p8_family.py`.

### `certificates/` — certificates of the infeasibility claims (SM S6, S9, S16, S18)

**(a) VeriPB: `d_ext` and the completeness of the lists** (`certificates/veripb/`, `code/veripb/`).
`records.jsonl` has one record per statement "no extended logical of weight `<= W` other than the listed ones":
`name`, `statement`, `source` (extended-code file), `basis`, `W`, `blocks` (list files), `opb_sha256` of the OPB
instance (`NAME.opb.gz`, shipped), `inst_sha256` of the search input (rebuilt by `code/veripb/build_opb.py`), the
proof-stream `proof_bytes` and `proof_sha256` (VeriPB 3.0 syntax, as written by `code/veripb/pbdfs.c` with `-F
cachemax`), the search result (`nodes`), the VeriPB verdict line and exit code and CPU times.  Proofs are **never
stored**: they are streamed from the generator to VeriPB and only their SHA-256 is kept (up to 4.6e11 bytes);
`code/veripb/certify.py check NAME` regenerates the stream, checks it and compares the hash.  Checker logs:
`certificates/veripb/logs/NAME.{veripb,search}.log`.  The encoding (in `code/veripb/build_opb.py`): one 0/1 variable per
extended column, every check row a linear equality with binary digits (`sum x - 2 sum 2^k a = 0`), logical rows with
a parity variable each, `sum q >= 1`, the weight bound, one clause per listed logical; the translation symmetry is
used inside the proof (redundance steps with the translation as witness), so the reduction to orbit
representatives is part of what VeriPB checks.  `code/veripb/check_opb.py` re-checks, independently of the encoder,
that each shipped OPB file encodes exactly the statement for the data files.

| records | statement | SM |
|---|---|---|
| `u11_{Z,X}_W9` | u11: `d_ext >= 10` (the 144 listed logicals give `d_ext = 10`) | S3, S6 |
| `u11_{Z,X}_W10` | u11: the extended logicals of weight `<= 10` are exactly the 144 listed | S3, S6 |
| `u11_{Z,X}_W11` | u11: those of weight `<= 11` are exactly the 144 + 7344 listed | S3, S6 |
| `bb90_{Z,X}_W7` | `[[90,8,10]]` class of c16 / c11 / c12 / c13: `d_ext >= 8` | S4, S6 |
| `bb90_{Z,X}_W8`, `bb90_{Z,X}_W9` | the extended logicals of weight `<= 8` (`<= 9`) are exactly the 585 (585 + 16830) listed | S4, S6 |
| `fig12_{Z,X}_W5..W8` | Fig. 12 order class: `d_ext >= 9` (`d_ext = 11` and the 4224 list rest on two exhaustive searches) | S6, S10 |

**(b) DRAT / LRAT: the extended-lift instances** (`certificates/proofs/lift_{u11,c11,c12,c13,c16}.jsonl`,
`lift_controls.jsonl`, `lift_instance_order.json`, `drat_lift/`, `logs/lift_*_logs.txt.gz`;
`code/proofs/ext_lift_certs.py`).  For a circuit with `d_ext = D`, a basis and `R`: every weight-`D` list entry with
at most one extra zero-image mechanism, and every weight-`(D+1)` entry, as a CNF (one variable per distinct detector
set of each column group, exactly one per group, at most one zero-image candidate, XOR of every touched detector = 0
by Tseitin chains); the instances of one `(circuit, basis, R)` are split into `K` batches (instance `i` in batch
`i mod K`) and combined by selector variables, so that a batch is unsatisfiable iff none of its instances lifts.  Each
batch was refuted by CaDiCaL with a DRAT proof, checked by drat-trim, whose LRAT core was checked by cake_lpr.  Each
record: `split [s, K]`, `instances`, `cnf_sha256`, `vars`, `clauses`, solver answer and CPU, `drat_bytes`,
`drat_sha256`, drat-trim verdict, `lrat_bytes`, `lrat_sha256`, cake_lpr verdict, DEM statistics, and `cnf_comment` (the
comment line of the CNF, part of its hash).  The CNFs are deterministic and are regenerated from the data files
(sha256 = record).  The DRAT proofs (49 GB for u11) are not shipped except for the smallest batches
(`drat_lift/*.drat.xz`, see section 5); the others are identified by their SHA-256.

| file | circuit | `R` | batches | instances | DRAT (total) | needed for every `R` |
|---|---|---|---|---|---|---|
| `lift_u11.jsonl` | u11 (`D = 10`, lists 144 + 7344) | 1–31 | 632 | 464 256 | 49 GB | `R' = 31` (End Matter, `code/p11/premises.py`) |
| `lift_c11.jsonl` | c11 (`D = 8`, lists 585 + 16830) | 1–25 | 986 | 870 750 | 53 GB | `R'_9 = 25` |
| `lift_c12.jsonl` | c12 | 1–12 | 310 | 417 960 | 12 GB | `R' = 12` (rounds separated) |
| `lift_c13.jsonl` | c13 | 1–12 | 310 | 417 960 | 11 GB | `R' = 12` |
| `lift_c16.jsonl` | c16 | 1–12 | 310 | 417 960 | 11 GB | `R' = 12` (SM S4 "All R") |
| `lift_controls.jsonl` | u16, u11_control_p10, `R = 1` | 1 | 34 | | | positive controls: SAT |

All batches: solver UNSAT, drat-trim `s VERIFIED`, cake_lpr `s VERIFIED UNSAT`.  Checker logs (CaDiCaL, drat-trim,
cake_lpr) are shipped for every batch except u11 `R <= 4` and c11 `R <= 12` (and 16 batches of c11, Z basis,
`R = 13`), whose logs were not kept; their verdicts and hashes are in the records, and the batches of u11 `R <= 4`,
c11 `R <= 2` and c12, c13, c16 `R = 1` were regenerated by the shipped script (section 5).

**(c) `[[90,8,10]]`: every per-check order has X-side `d_ext <= 8`** (SM S4): `certificates/bb90_dext_free/X_side.cnf.gz`
(3555 variables, 21690 clauses, sha256 of the uncompressed file
`f9e93bdfea46ad484401fa08b79c017e70aa7f1446431f7f4ae849351cc643c6`), written by `code/bb90/dext_free.py` (an
encoding independent of the rest of the package; it regenerates the CNF byte-identically and re-verifies each of the
17 910 conflict combinations as an explicit extended logical of weight `<= 8`); record
`certificates/proofs/bb90_dext_free.jsonl`, logs `certificates/proofs/logs/bb90_dext_free__X_side.*`:

| step | result | CPU |
|---|---|---|
| CaDiCaL 3.0.1 (`-q --binary=true`), binary DRAT proof | UNSAT; proof 2 621 607 032 bytes, sha256 `5fad1f63366a1ff468273d9712b4ead9157e35d05ec7570d4f9faedb80dbceb0` | 1624 s |
| drat-trim (backward checking, LRAT core written) | `s VERIFIED` (19 080 of 21 690 clauses and 16 549 928 of 32 220 313 lemmas in the core) | 1667 s |
| cake_lpr on the LRAT core (8 487 007 903 bytes, sha256 recorded) | `s VERIFIED UNSAT` | 236 s |

The proof is not shipped; `python code/proofs/check_proofs.py --records certificates/proofs/bb90_dext_free.jsonl
--regenerate all --timeout 20000` regenerates and checks it (on the reference machine byte-identical; about 1 CPU
hour and 12 GB of disk).

**(d) Fig. 12, its retimings and circuits A, B, C** (SM S9, S13, S16; unchanged from version 1.1).  Each instance:
`NAME.cnf.gz` (DIMACS; the header states what it encodes and which clauses are the family encoding and which are
CEGAR nogoods), `NAME.log.json` (description, counts, sha256 of the uncompressed CNF, results and CPU times of a
from-scratch re-solve with CaDiCaL 1.5.3, Glucose 4 and MiniSat 2.2 — Glucose and MiniSat with a conflict budget,
`UNKNOWN` = budget exhausted — and, for CEGAR instances, `family_only`: the family encoding alone is satisfiable), and
for CEGAR instances `NAME.varmap.json.gz` (variable id -> encoder object).

| directory | paper statement |
|---|---|
| `min_period_primary_encoding/P08..P17_pipelined`, `P20_common_frame` | SM S16 "Minimum period": pipelined schedules with P = 8, ..., 17 and common-frame schedules with P = 20 are unsatisfiable (colour-symmetric family, Fig. 12 order class) |
| `min_period_second_encoding/P08..P17_pipelined` | SM S16: a second, independent encoding agrees for P = 8, ..., 17 |
| `less_symmetry/P08..P11_subgroup_1_2`, `P08_subgroup_{0_3,6_0,6_3,4_2}` | SM S16 "Less symmetry": invariance under the order-12 subgroup generated by (1,2) excludes P <= 11; any non-trivial subgroup excludes P = 8 (the four minimal non-trivial subgroups of the 24 colour-preserving translations) |
| `window_explanation/P24_window14_{X0,Z2}` | SM S16: restricting the window of class X0 or Z2 to at most 14 steps is unsatisfiable at P = 24 (explanation only) |
| `order_class_uniqueness/*` | SM S16 "Uniqueness of the order class": 24 colourings x 2 residual types, UNSAT after blocking the translates of Fig. 12; the 3859 witnesses behind the nogoods are in `witnesses.json.gz` (`code/check_uniqueness_witnesses.py`) |
| `fig12_retimings/*` | Table S5 (retimings that keep the Fig. 12 orders), all modelled logicals |
| `fig12_retimings_len2only/*` | Table S5, proven direction: the same 25 rows with the frame model restricted to the 360 "ten data + one length-2 residual" logicals, for which "frame-model lift => genuine undetected error" is proven (SM S9); 25/25 UNSAT |
| `frame_model_samples/*.json.gz` | SM S16 "Soundness of the clauses": the 991 + 99 sampled cases (`code/sat/soundness.py`) |
| `proofs/certificates_proofs.jsonl`, `proofs/drat/*.drat.xz`, `proofs/logs/` | the DRAT proofs of these 129 CNFs (104 + 25): 129/129 UNSAT, drat-trim `s VERIFIED`, cake_lpr `s VERIFIED UNSAT`; the 115 proofs up to 100 MB are shipped (1056 MB uncompressed, 256 MB xz), the 14 larger ones by sha256 (`code/proofs/check_proofs.py --regenerate unshipped`) |
| `proofs/lift_circuit_{A,B,C}.jsonl`, `proofs/logs/lift_circuit_{A,B,C}_logs.txt.gz`, `proofs/lift_control.txt` | SM S13 "Certificates": the lift batches of circuits A (`R <= 32`, 544 batches), B (`R <= 24`, 312), C (`R <= 14, 16`, 128), all UNSAT with drat-trim and cake_lpr verified; positive control Fig. 12 `R = 1` (4224/4224 SAT) |

The re-solve table of version 1.1 ("which solver proved each certificate") is reproduced by
`code/check_certificates.py`; CaDiCaL 1.5.3 proves every instance without a budget, Glucose / MiniSat within their
budgets for most of them (per instance in `NAME.log.json`).  Meaning of UNSAT for the period families: every legal
deterministic circuit of the family has a weight-11 undetected error for sufficiently many rounds (bulk Pauli-frame
model, SM S9, S16).  Not certified: `d_ext = 11` and the completeness of the 4224 list of Fig. 12 (two independent
exhaustive searches, `code/dext/`; a CNF encoding is out of reach for CDCL already at weight 6), the per-logical lift
decisions of the version-1 scripts (exact SAT / CP-SAT calls without proof output; the DRAT records above cover the
same instances), and the direct DEM searches (SM S5).

### `logs/dcirc/` and `code/dcirc/reference_runs.tsv` — direct search on the DEM (SM S5)
One log per run of `code/dcirc/ccsearch.c` in decide mode (`CIRCUIT_BASIS_R<R>_W<W>.txt`): a header, one
`ORBIT o size s nodes n sols k cpu t` line per root case (runs split over processes are merged), the `SOL` line of a
found solution, and the result.  145 runs: gross circuit A (`R = 1`: `W = 11` NONE, `W = 12` FOUND; `R = 2, 3`, `W = 11`
NONE), c16 (`R = 1..12`, `W = 9` NONE; `R = 1..3`, `W = 10` FOUND), u16; **c11, c12, c13** (`R = 1..12`, `W = 9` NONE;
`R = 1..3`, `W = 10` FOUND); **u11** (`R = 1, 2`, `W = 11` NONE; `R = 1`, `W = 12` FOUND) and the period-10 control
(`W = 11` FOUND).  `reference_runs.tsv` lists status, root cases, node count and CPU seconds; the instances written by
the shipped exporter are byte-identical to those of the logged runs (checked for A `R = 1`, c16 `R = 1, 3, 12`, c11
`R = 1, 12`, c12 and c13 `R = 1`, u11 `R = 1, 2`, control `R = 1`).  The second implementation (`code/p11/direct.py`,
meet-in-the-middle terminal) was run for u11 at `R = 1` (section 6).

### `data/ler/` — logical-error-rate data (SM S7, S8)
sinter CSV files (one row per batch of shots of one task; `json_metadata` = circuit, basis, `R`, `p`, noise model;
`strong_id` = sinter's hash of circuit, DEM, decoder and metadata) and summaries:

| directory | content | paper |
|---|---|---|
| `sd6_lambda_bb90/` | c11, c13, c16 and IBM's circuit (`bb90_ibm_depth8.json`), `R = 10`, `lam0`, `lam0.1`, `lam1`, `p = 1.5e-3 .. 5e-3`, BP-OSD and Relay-BP; `summary.json` / `summary.txt` (per-round rates, Jeffreys intervals, ratios) | SM S7 "[[90,8,10]]", main text |
| `sd6_lambda_gross/` | u11 vs Fig. 12 and IBM's circuit, `R = 12`; `earlier/`: the identical Fig. 12 / IBM tasks of an earlier sampling, pooled (only fig12 / ibm rows kept) | SM S7 "Gross code" |
| `neutral_atom/` | `main.csv` (sets cur, cur x 0.5, proj), `sens.csv` (sensitivity variants), gross `R = 12`, `[[90,8,10]]` `R = 10`; `summary.json` / `summary.md` | SM S8, Tables S3, S4 |
| `independent_resampling/` | the second, independently written pipeline (own circuits, noise and decoder calls): per-job counts (`*_jobs.jsonl`) and summaries; the paper's pooled values (e.g. 0.52 [0.44, 0.62] and 0.64 [0.48, 0.85] at `lambda = 0`, `p = 3e-3`) | SM S7, S8 |

Per round: `eps = eps_Z + eps_X`, `eps_b = 1 - (1 - P_b)^(1/R)`; 95% Jeffreys intervals by beta-posterior Monte Carlo
(40000 draws, seed 1), ratios from the same draws.  Shot numbers of the neutral-atom blocks were fixed in advance.
Decoders (`code/ler/decoders.py`): BP-OSD (min-sum, 10000 iterations, OSD-CS order 7) and Relay-BP, identical
parameters for every circuit.

---------------------------------------------------------------------------------------------------------------------

## 4. Map from the paper to the files

| paper | statement | data | scripts |
|---|---|---|---|
| Table I, SM S3 "Circuit" | u11 legal, deterministic, translation invariant, timing of Table I | `data/circuits/u11.json` | `code/p11/check_circuits.py u11` |
| SM S3 "Non-segmentability", Fig. 1(a) | mixed-type strongly connected components, the 6-cycle `X9 -> Z17 -> X12 -> Z20 -> X22 -> Z24 -> X9`; the segmented control has none | `u11.json`, `u11_control_segmented.json` | `code/p11/check_circuits.py u11 u11_control_segmented` |
| SM S3 "Order class and lists" | 360 columns, 5 orbits; `d_ext = 10`; exactly 144 / 7344 | `data/extended_code/u11_*`, `data/logicals/u11_*` | `code/veripb/certify.py check u11_*`, `code/veripb/check_opb.py` |
| Lemma 1, SM S2 "Computed check" | every DEM mechanism has image 0 or one extended column, template identity | | asserted by every lift script (`code/p11/lift.py`, `code/lift.py`, `code/bb90/lift.py`) |
| Lemma 2, Theorem 1, SM S3 "Lift" | for `R = 1..31`, both bases: none of the 144 (with or without one readout flip) and 7344 lifts | lists | `code/p11/lift.py --circuit u11 --R 1-31`; certificates `lift_u11.jsonl`, `code/proofs/ext_lift_certs.py u11` |
| SM S3 "Positive controls" | period-10 control: 432 (Z) / 576 (X) weight-11 lifts at `R = 1, 2`; segmented control: all lift | | `code/p11/lift.py --circuit u11_control_p10 --R 1-2`, `--circuit u11_control_segmented --R 1` |
| End Matter "All rounds for Theorem 1", SM S3 "All R" | `S = 1`, `Delta = 10`, `G = 31`, span 300, insertion at `x in [1, 11(R-1)]`, `R' = 31` | | `code/p11/premises.py --circuit u11 --rins 2-16` |
| Theorem 1, SM S3 "upper bound" | weight-12 data logicals, `R = 1, 2, 3, 6, 10, 31` | `witnesses/upper_bound_weight12.json` | `code/p11/inject_upper_bound.py u11` |
| Theorem 1, SM S5 "Period-11 circuits" | direct DEM search: no undetected logical of weight `<= 11` at `R = 1, 2`; control 11 | `logs/dcirc/u11_*` | `code/p11/direct.py run u11 Z 1 11`; `code/dcirc/run.py one u11 Z 2 11` |
| Table I, Theorem 2, SM S4 "Period-11 and period-12 circuits" | c11 / c12 legal, deterministic, invariant, extended code = that of c16 | `bb90_c11.json`, `bb90_c12.json` | `code/p11/check_circuits.py c11 c12 c13` |
| Theorem 2, End Matter "Details for Theorem 2" | c11: lifts zero for `R = 1..25`, both bases; `G = 31`, `R'_8 = 22`, `R'_9 = 25`; weight-10 injection | `bb90_weight{8,9}_*` | `code/p11/lift.py --circuit c11 --R 1-25`, `code/p11/premises.py --circuit c11`, `code/p11/inject_upper_bound.py c11`; certificates `lift_c11.jsonl` |
| SM S4 (c12) | rounds separated, `R' = 12`, lifts zero for `R <= 12` | | `code/p11/premises.py --circuit c12 --separated`, `code/p11/lift.py --circuit c12 --R 1-12`; `lift_c12.jsonl` |
| SM S4 "Lists", SM S6 | `d_ext = 8`, exactly 585 / 16830 | `bb90_*` | `code/veripb/certify.py check bb90_*`; `code/bb90/lists.py --wmax 9` (meet-in-the-middle) |
| SM S4, Table S1 (c16) | legality, lift `R <= 12`, separation and periodicity, weight-10 injection, controls u16 / s16 | `bb90_c16.json`, `bb90_u16.json`, `bb90_s16.json` | `code/bb90/*.py` (section 6); `lift_c16.jsonl` |
| SM S4 "Every choice of orders has `d_ext <= 8`" | the per-check-free CNF is UNSAT | `certificates/bb90_dext_free/` | `code/bb90/dext_free.py`, `code/proofs/check_proofs.py --records certificates/proofs/bb90_dext_free.jsonl` |
| SM S4 "Family bound", End Matter | P <= 10 obstructed within the four `d_ext = 8` order classes (48 SAT instances) | — | not included (see section 7) |
| SM S5 | direct searches: A `R <= 3`, c16 `R <= 12`, c11 / c12 / c13 `R <= 12` (`W = 9` NONE), u11 `R <= 2` | `logs/dcirc/` | `code/dcirc/run.py`, `code/p11/direct.py` |
| SM S6 | every infeasibility claim of both theorems has a checked certificate | `certificates/veripb/`, `certificates/proofs/lift_*` | `code/veripb/`, `code/proofs/ext_lift_certs.py` |
| SM S7 | ratios at `lambda = 0, 0.1, 1`; IBM / Fig. 12 references | `data/ler/sd6_lambda_*`, `independent_resampling/` | `code/ler/tables.py`, `code/ler/sample_one.py` |
| SM S7 "IBM's gross circuit" | exactly 144 (Z) / 288 (X) undetected logicals of weight 10 per round, none lighter, `R <= 3` | — | not included (enumeration logs; section 7) |
| SM S8, Tables S2–S4 | neutral-atom model and ratios | `data/ler/neutral_atom/` | `code/ler/na_noise.py`, `code/ler/tables.py` |
| Corollary 1, SM S9, S10 | Fig. 12: `d_ext = 11`, 4224 logicals, all lift; retimings | `data/logicals/weight11_*`, `witnesses/weight11_*` | `code/dext/run_dext.sh`, `code/verify_witnesses.py`, `code/lift.py --circuit fig12` |
| Table S5, SM S9 | retimings keeping the Fig. 12 orders are obstructed | `certificates/fig12_retimings*/` | `code/sat/len2only.py`, `code/sat/regenerate.py`, `code/proofs/check_proofs.py` |
| SM S11, S12, Tables S6–S8 | circuits A, B, C: legality, interleaving, extended code = Fig. 12's | `circuit_{A,B,C}.json` | `code/check_circuits.py A B C fig12`, `code/class_table.py` |
| SM S13 | lift A `R <= 32`, B `R <= 24`, C `R <= 14, 16`; three implementations; DRAT certificates | | `code/lift.py`, `code/compare_lifts.py`, `code/proofs/run_lift_certs.py` |
| SM S14 | round reduction for A (gap `G = 52`, `R' = 32`), B (slab premise), C (separated) | | `code/premises.py` |
| SM S15 | weight-12 injection for A, B, C | `witnesses/upper_bound_weight12.json` | `code/inject_upper_bound.py A B C` |
| SM S16 | search and optimality, minimum period, uniqueness, completeness and soundness checks | `certificates/*` | `code/check_certificates.py`, `code/sat/*`, `code/p8_family.py`, `code/check_uniqueness_witnesses.py` |
| SM S17 | idle sensitivity of the period-18 circuit | — | not included (version 1 data set had none either) |

Lemma 1 and the deletion / splitting arguments of the round reductions are pen-and-paper (End Matter, SM S2, S4,
S14); the scripts check their premises on the actual circuits.  Theorem 1 then follows: `d_ext = 10` (VeriPB) excludes
weight `<= 9`; by Lemma 2 an undetected logical of weight 10 or 11 is one of the three lifted cases, none of which
lifts for `R <= 31` (CaDiCaL / DRAT for every instance; independently `code/p11/lift.py`); the gap argument maps every
`R` to `R <= 31`; the weight-12 injection gives the upper bound.  Theorem 2 likewise with `d_ext = 8`, the lists of 585
and 16830, `R <= 25`, and the weight-10 injection.

---------------------------------------------------------------------------------------------------------------------

## 5. Solvers, certificates and checkers

| statement | encoding (generator) | solver / proof producer | checker | verdict rule | proofs |
|---|---|---|---|---|---|
| `d_ext`, list completeness (u11, `[[90,8,10]]`; Fig. 12 `>= 9`) | OPB with native parity rows (`code/veripb/build_opb.py`), 20 instances | `code/veripb/pbdfs.c` (deterministic, untrusted) | VeriPB 3.0.2 | output line `s VERIFIED UNSATISFIABLE` **and** exit code 0 **and** search `RESULT UNSAT` (VeriPB also exits 0 on `s VERIFIED NO CONCLUSION`) | streamed, SHA-256 only (largest 4.6e11 bytes) |
| extended lift u11 / c11 / c12 / c13 / c16 | CNF (`code/proofs/ext_lift_certs.py`), 2548 batches | CaDiCaL 3.0.1, binary DRAT | drat-trim (backward), cake_lpr on the LRAT core | `s VERIFIED` and `s VERIFIED UNSAT` (cake_lpr exits 0 also on failure) | SHA-256 (136 GB in total); smallest batches shipped |
| lift A / B / C, Fig. 12 SAT certificates, `[[90]]` `d_ext <= 8` | CNF (`code/proofs/lift_cnf.py`, `code/sat/`, `code/bb90/dext_free.py`) | CaDiCaL 3.0.1 | drat-trim, cake_lpr | as above | 115 shipped, others SHA-256 |
| direct DEM searches | — | `ccsearch.c`, `code/p11/mitm.c` | — | exhaustive search, no certificate | logs |

VeriPB runs (`certificates/veripb/records.jsonl`; reference machine, Apple M-series, CPU = generator + checker):

| record | nodes | proof stream | VeriPB time total (s) | generator + checker CPU (s) | run |
|---|---|---|---|---|---|
| `fig12_Z_W5` | 3.39e+04 | 14.2 MB | 3 | 1 | package pipeline |
| `fig12_Z_W6` | 2.02e+05 | 36 MB | 1 | 2 | package pipeline |
| `fig12_Z_W7` | 1.46e+06 | 213 MB | 6 | 10 | package pipeline |
| `fig12_Z_W8` | 9.5e+06 | 1.45 GB | 49 | 80 | package pipeline |
| `fig12_X_W5` | 3.24e+04 | 14.7 MB | 0 | 0 | package pipeline |
| `fig12_X_W6` | 2.03e+05 | 35.2 MB | 1 | 2 | package pipeline |
| `fig12_X_W7` | 1.42e+06 | 198 MB | 6 | 10 | package pipeline |
| `fig12_X_W8` | 9.24e+06 | 1.38 GB | 51 | 84 | package pipeline |
| `bb90_Z_W7` | 5.4e+05 | 72.8 MB | 2 | 4 | package pipeline |
| `bb90_Z_W8` | 4.76e+06 | 701 MB | 25 | 37 | package pipeline |
| `bb90_Z_W9` | 4.7e+07 | 7.87 GB | 639 | 650 | reference run, re-run identical (379 CPU s) |
| `bb90_X_W7` | 7.26e+05 | 102 MB | 3 | 6 | package pipeline |
| `bb90_X_W8` | 5.96e+06 | 902 MB | 33 | 53 | package pipeline |
| `bb90_X_W9` | 5.57e+07 | 9.52 GB | 378 | 609 | package pipeline |
| `u11_Z_W9` | 3.48e+07 | 5.55 GB | 246 | 450 | package pipeline |
| `u11_Z_W10` | 2.67e+08 | 46.6 GB | 5251 | 5128 | reference run |
| `u11_Z_W11` | 2.14e+09 | 456 GB | 13684 | 25631 | reference run, -F 1000000 |
| `u11_X_W9` | 3.43e+07 | 5.37 GB | 248 | 448 | package pipeline |
| `u11_X_W10` | 2.65e+08 | 46.2 GB | 4885 | 4764 | reference run, re-run identical (3626 CPU s) |
| `u11_X_W11` | 2.16e+09 | 425 GB | 25015 | 40757 | reference run |

Every record: `s VERIFIED UNSATISFIABLE`, exit code 0, search `RESULT UNSAT`.  "reference run": the streamed run that
produced the recorded hash (same `pbdfs.c` up to comments); "package pipeline": run with `code/veripb/certify.py` of
this package; "re-run identical": regenerated by `certify.py check`, stream hash equal to the record.  The node
counts of the u11 and `[[90,8,10]]` records equal those of separate count-only runs of the same search.

**Memory.** VeriPB keeps every live constraint in memory (about 2–4 KB each).  The weight-11 u11 proofs need about
**18 GB** of memory with the generator's bounded clause cache `-F 1000000` (the recorded Z-basis run); the recorded
X-basis run was generated with `-F 0` and needed about 40 GB.  `code/veripb/certify.py check u11_X_W11 --cachemax
1000000` checks a new proof of the same statement within about 18 GB (its hash then differs from the record and is
reported, not compared).  The weight-10 proofs need a few GB; everything else less than 1 GB.

Shipped DRAT proofs of the extended lift: the 106 batches of u11 `R <= 4`, c11 `R <= 2` and c12, c13, c16 `R = 1` whose
proof is at most 5 MB (`certificates/proofs/drat_lift/`, 4 MB xz; `ext_lift_certs.py shipped` checks them against the
regenerated CNFs).  Regeneration with this package on the reference machine (`ext_lift_certs.py`, these 160 batches
and the 10 control batches): every CNF and every DRAT proof byte-identical to the record, all UNSAT (controls SAT),
drat-trim and cake_lpr verified; the records carry the result in the field `rerun`.

---------------------------------------------------------------------------------------------------------------------

## 6. Expected output and runtimes

Single-core CPU times on an Apple M-series laptop (stim 1.16.0, ortools 9.15); the machine was shared, so wall times
were longer.

| command (period-11 part) | expected result | CPU time |
|---|---|---|
| `code/p11/check_circuits.py u11 u11_control_p10 u11_control_segmented c11 c12 c13` | 48 `PASS` lines (timing = Table I; 3 mixed-type components for u11 and c11, none for the segmented control) | 11 s |
| `code/p11/lift.py --circuit u11 --basis Z --R 1-31` (and `X`) | 31 x `PASS ... w10 0/144, w10+zero-image 0/144, w11 0/7344` | 42 min per basis (`R = 31`: about 3 min) |
| `code/p11/lift.py --circuit c11 --basis Z --R 1-25` (and `X`) | 25 x `PASS ... w8 0/585, w8+zero-image 0/585, w9 0/16830` | 43 min per basis |
| `code/p11/lift.py --circuit c12` / `c13 --R 1-12` | 12 `PASS` lines per basis | about 6 min per basis (as c16) |
| `code/p11/lift.py --circuit u11_control_p10 --R 1-2` / `u11_control_segmented --R 1` | weight-11 lifts 432 (Z) / 576 (X); all 144 / 144 / 7344 | 10 s |
| `code/p11/premises.py --circuit u11 --rins 2-16` | `S = 1`, `Delta = 10`, `G = 31`, insertion at `x in [1, 11R]`, `R'_10 <= 28`, `R'_11 <= 31` | 2.4 min |
| `code/p11/premises.py --circuit c11 --rins 2-15` | `G = 31`, `R'_8 <= 22`, `R'_9 <= 25` | 1.3 min |
| `code/p11/premises.py --circuit c12 --separated` (and `c13`) | rounds separated, `R' <= 12` | 1 min |
| `code/p11/inject_upper_bound.py u11 c11 c12 c13` | 46 `PASS` lines | 1.5 min |
| `code/p11/direct.py selftest` | 1 `PASS` line | 5 s |
| `code/p11/direct.py run u11 Z 1 11` / `u11 X 1 11` | NONE, 12 root cases, 1.06e10 / 1.12e10 nodes | 10 / 8 min |
| `code/p11/direct.py run u11_control_p10 Z 1 11` | FOUND (weight 11, re-verified) | 6.5 min |
| `code/dcirc/run.py one c11 Z 12 9` (and the other logs of `logs/dcirc/`) | NONE, node count = reference | see `code/dcirc/reference_runs.tsv` (c11 `R = 12`: 9–15 min) |
| `code/veripb/check_opb.py` | 20 `PASS` lines | 16 s |
| `code/veripb/certify.py opb all` | 20 `PASS` lines (OPB and search input rebuilt, sha256 = record = shipped) | 2 min |
| `code/veripb/certify.py check NAME` | `PASS ... 's VERIFIED UNSATISFIABLE' yes, exit code 0 ...` | see the VeriPB table (section 5); u11 W = 10: 1 h, W = 11: 7–11 h, 18–40 GB |
| `code/proofs/ext_lift_certs.py u11 1-4 OUT` | 40 batches + 1 summary `PASS`, CNF (and DRAT) sha256 = record | 5 min |
| `code/proofs/ext_lift_certs.py u11 1-31 OUT --workers 4` / `c11 1-25` / `c12`, `c13`, `c16 1-12` | one `PASS` per batch (632 / 986 / 310 each) | about 5 / 6 / 1.5 h each (tools, from the records) plus CNF generation |
| `code/proofs/ext_lift_certs.py shipped OUT` | 106 `PASS` lines + summary | 1 min |
| `code/ler/tables.py` | 4 `PASS` lines and the ratios of SM S7 / S8 | 2 s |
| `code/ler/tables.py --verify-circuits 0` | every one of the 132 / 162 / 100 sampled tasks has the recorded sinter strong_id | 9.5 min |
| `code/ler/sample_one.py` | e.g. `6.62 [4.1, 10.6]` vs recorded `7.65 [5.98, 9.75]` (c11 / IBM, `lambda = 1`, `p = 4e-3`, BP-OSD; random) | 3 min |


| command (version 1 parts) | expected result | CPU time |
|---|---|---|
| `code/check_circuits.py A B C fig12` | 45 `PASS` lines | 0.5 min |
| `code/lift.py --circuit A --basis Z X --R 1-32` | 64 x `PASS ... 0/4224` | about 1 h |
| `code/lift.py --circuit fig12 --basis Z X --R 1` | 2 x `PASS ... 4224/4224` | 6 s |
| `code/premises.py --circuit A` | `G = 52`, insertion at `x in [4, 18R]`, `R' <= 32` | 40 s |
| `code/inject_upper_bound.py A B C` | 32 `PASS` lines | 1.5 min |
| `code/verify_witnesses.py` | 55 `PASS` lines (25 344 + 48 + 944 fault sets) | 22 min |
| `code/check_certificates.py` | 129 `PASS` lines, all `UNSAT` | 55 min |
| `code/proofs/check_proofs.py` | 115 `PASS ... drat-trim VERIFIED`, 14 `skip` (not shipped) | 10 min |
| `code/proofs/check_proofs.py --regenerate unshipped` | 14 `PASS` lines | 2.9 h |
| `code/proofs/run_lift_certs.py A 1-32 ...` / `B 1-24` / `C 1-14,16` | one `PASS` per batch (544 / 312 / 128) | 6 h / 2.6 h / 1.2 h |
| `code/compare_lifts.py` | 16 `PASS` lines, identical sets for CP-SAT, DP and MITM | 4 min |
| `code/sat/len2only.py NAME` (25 names) | `PASS IDENTICAL` | 12 min in total |
| `code/dext/run_dext.sh w10` / `w11` | `PASS d_ext >= 11` / `PASS weight-11 list` (4224) | 20 min / 1 h |
| `code/bb90/check_circuits.py c16 u16 s16` | 22 `PASS` lines | 5 s |
| `code/bb90/lists.py --wmax 9` | 18 `PASS` lines | 4.5 min |
| `code/bb90/lift.py --circuit c16 --basis Z X --R 1-12` | 24 x `PASS ... 0/585, 0/585, 0/16830` | 12 min |
| `code/bb90/premises.py --rmax 14` | 4 `PASS` lines | 70 s |
| `code/bb90/dext_free.py OUT.cnf --compare ...` | `PASS ... byte-identical` | 4 min |
| `code/dcirc/run.py quick` / `full` | 9 / 25 `PASS` lines | 40 s / 45 min |

---------------------------------------------------------------------------------------------------------------------

## 7. Scope, limitations, and what is not included

All statements are for the template of `code/gross12/schedule.py` (single ancilla per check, CNOT gates, memory
experiments) and SD6 noise with independent single-operation faults counted as DEM mechanisms; lower bounds hold for
every sub-model of SD6.  The certificates certify that the clause sets / OPB instances are unsatisfiable; that they
encode the stated questions is argued in the paper and checked by the scripts (independent implementations, the
semantic check of the OPB files, regeneration from the data files).  The reductions to these finite problems (Lemma 1,
Lemma 2, the round reductions) are mathematical arguments whose premises are verified by the scripts.  The
logical-error-rate comparisons hold for the two decoders used and the stated noise models; the neutral-atom model
rests on the assumptions listed in SM S8.

Not included: the SAT searches that found the circuits and the family bound "P <= 10 obstructed" for `[[90,8,10]]`
(SM S4 "Family bound": 48 bulk Pauli-frame instances, no certificate); the random-schedule control of SM S3 ("about
one in 70"); the exact enumeration of the weight-10 logicals of IBM's gross circuit and of the weight-12 logicals of
u11 (SM S7; counts stated in the paper); the leading-order estimates; the idle-noise study of the period-18 circuit (SM
S17); the morphing end-cycle code (SM S19); the DRAT proofs larger than the shipping limit and every VeriPB proof
(identified by SHA-256, regenerated by the scripts); the checker logs of the lift batches named in section 3 (b).
