"""Audit driver: run a candidate program source (file) through evaluate_decoder.
Usage: drive.py <task_id> <split> <shots> <candidate.py> [workers]
Prints status, counts, speed, diagnostics.
"""
import sys, os
from evaluators.decoder_eval import evaluate_decoder

task_id, split, shots, path = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
workers = int(sys.argv[5]) if len(sys.argv) > 5 else 1
src = open(path).read()
rep = evaluate_decoder(task_id, src, split=split, shots=shots, submit=False, num_workers=workers)
print(rep.to_text())
print("STATUS", rep.status, "os_sandbox", rep.os_sandbox)
print("COUNTS", rep.counts)
print("SPEED", rep.speed)
