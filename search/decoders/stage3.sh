#!/bin/zsh
# E-006 stage 3: fixed-weight sampling (method b).
# (surf5_p0.004 validation done in the first launch; bb72_p0.001 first launch with sub-low 1.0 kept w=2 (8000) and
#  w=3 batches 0-13; relaunched with cheaper reference subsampling)
cd /Users/ephemeral/Desktop/qec-ai-search
F() { uv run python -m search.decoders.run_fixedweight "$@"; }
F --code bb72 --p 0.001 --w 2:16 --n 1000 --n-low 2=8000,3=7000,4=6000,5=6000,6=6000,7=3000,8=3000,9=3000,10=3000 --batch 500 --sub 0.25 --sub-low 0.2 --low-w 6 --workers 6
F --code bb72 --p 0.002 --w 2:22 --n 700 --n-low 2=4000,3=4000,4=4000,5=4000,6=4000,7=2000,8=2000,9=2000,10=2000,11=2000 --batch 500 --sub 0.25 --sub-low 0.2 --low-w 6 --workers 6
F --code bb90 --p 0.001 --w 3:26 --n 500 --n-low 3=3000,4=3000,5=3000,6=3000,7=3000,8=3000,9=1500,10=1500,11=1500,12=1500,13=1500,14=1500 --batch 250 --sub 0.1 --workers 6
F --code bb90 --p 0.002 --w 3:40 --n 300 --n-low 3=2000,4=2000,5=2000,6=2000,7=2000,8=2000,9=1000,10=1000,11=1000,12=1000,13=1000,14=1000,15=1000,16=1000 --batch 250 --sub 0.1 --workers 6
