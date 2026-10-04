#!/bin/zsh
# E-006 stage 4: BB90 fixed-weight sampling (method b). Waits for the orphaned bb72 p=0.002 run (PID given) to exit.
cd /Users/ephemeral/Desktop/qec-ai-search
while kill -0 $1 2>/dev/null; do sleep 15; done
F() { uv run python -m search.decoders.run_fixedweight "$@"; }
F --code bb90 --p 0.001 --w 3:26 --n 400 --n-low 3=3000,4=3000,5=3000,6=3000,7=3000,8=3000,9=1500,10=1500,11=1500,12=1500,13=1500,14=1500 --batch 250 --sub 0.1 --workers 6
F --code bb90 --p 0.002 --w 3:32 --n 200 --n-low 3=1500,4=1500,5=1500,6=1500,7=1500,8=1500,9=600,10=600,11=600,12=600,13=600,14=600,15=600,16=600 --batch 100 --sub 0.05 --trigger relay5 --workers 6
