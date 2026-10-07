#!/bin/bash
# 一键复现项目中经 auditor 复核的电路距离定理（auditor 2026-10-05 问题 2：证明须能由一条命令复现）。
#
#   bash scripts/reproduce_theorems.sh               # BB108、E-015 四个定理、IBM [[72,12,6]]（约 1 CPU 小时）
#   bash scripts/reproduce_theorems.sh --with-gross  # 另加 gross Fig. 12 d_circ = 11（W=10，约 4 CPU 小时）
#
# 每个定理 d_circ = w 的检验方式（下界依据 Strikis 等 arXiv 2603.05481 Prop. 3）：
#   1) 扩展码实例上 W = w-1 的完整 DFS：全部轨道情形 found=0，且 SUMMARY 行数 = 情形数（防止崩溃被漏算）；
#   2) 阳性对照：W = w 时 DFS 能找到解。
# 上界（注入验证的权重 w 见证）见各日志与审计报告，这里不重跑。
set -u
cd "$(dirname "$0")/.."
P=${P:-4}
OUT=results/reproduce_theorems
mkdir -p "$OUT"
cc -O3 -o "$OUT/dfs128" search/experiments/e014/dfs128.c || exit 1
FAIL=0

prove() {  # prove <name> <inst128> <w>
  local name=$1 inst=$2 w=$3
  local no; no=$(head -1 "$inst" | awk '{print $3}')
  local dir="$OUT/$name"; mkdir -p "$dir"
  seq 0 $((no - 1)) | xargs -P "$P" -I{} sh -c "'$OUT/dfs128' '$inst' $((w - 1)) {} > '$dir/W$((w - 1))_c{}.txt'"
  local nsum found
  nsum=$(cat "$dir"/W$((w - 1))_c*.txt | grep -c '^SUMMARY')
  found=$(cat "$dir"/W$((w - 1))_c*.txt | grep '^SUMMARY' | sed 's/.*found=\([0-9]*\).*/\1/' | paste -sd+ - | bc)
  local ctrl=0 cf pid
  for c in $(seq 0 $((no - 1))); do
    # 找到第一个解即按 PID 停止（DFS 在打印 50 个解后会静默跑完整个情形，不能等它自然结束）
    cf="$dir/W${w}_control_c$c.txt"
    "$OUT/dfs128" "$inst" "$w" "$c" > "$cf" 2>&1 &
    pid=$!
    while kill -0 "$pid" 2>/dev/null && ! grep -q '^FOUND' "$cf"; do sleep 1; done
    kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null
    if grep -q '^FOUND' "$cf"; then ctrl=1; break; fi
  done
  if [ "$nsum" -eq "$no" ] && [ "$found" -eq 0 ] && [ "$ctrl" -eq 1 ]; then
    echo "PASS  $name: no logical of weight <= $((w - 1)) ($no orbit cases), weight-$w control found"
  else
    echo "FAIL  $name: summaries $nsum/$no, found(W=$((w - 1)))=$found, control(W=$w)=$ctrl"; FAIL=1
  fi
}

to128() { awk 'NR==1{print; next} NF==3{print $1, 0, $2, $3; next} {print}' "$1" > "$2"; }

echo "== E-013  [[108,8,10]] 两色电路 d_circ = 10"
PYTHONPATH=. uv run python research/audits/2026-10-05-E-013-scripts/extcode.py > "$OUT/bb108_build.log" 2>&1 || { echo "FAIL build"; FAIL=1; }
for k in X Z; do to128 "results/E-013-audit/inst_$k.txt" "$OUT/bb108_$k.txt"; prove "bb108_$k" "$OUT/bb108_$k.txt" 10; done

echo "== E-015  LRC 电路定理（auditor 独立构造的实例 b6_theorems.py）"
for spec in bb72:6 cp126:9 bb120p:10 bb124:9; do
  name=${spec%%:*}; w=${spec##*:}
  PYTHONPATH=.:tests uv run python research/audits/2026-10-05-E-014-E-015-scripts/b6_theorems.py "$name" build > "$OUT/${name}_build.log" 2>&1 || { echo "FAIL build $name"; FAIL=1; continue; }
  for k in X Z; do prove "${name}_$k" "results/E-014-E-015-audit/b6_${name}_$k.txt" "$w"; done
done

echo "== E-015  IBM [[72,12,6]] 原电路 d_circ = 6（R = 1..8；任意 R 的论证见 research/audits/2026-10-05-E-014-E-015.md）"
PYTHONPATH=.:tests uv run python search/experiments/e015/ibm_lift.py --code bb72 --task bb72-dcirc --w 5 --R 1 2 3 4 5 6 7 8 \
  > "$OUT/ibm72_lift.log" 2>&1 || { echo "FAIL ibm_lift"; FAIL=1; }
tail -12 "$OUT/ibm72_lift.log"

if [ "${1:-}" = "--with-gross" ]; then
  echo "== E-014  gross Fig. 12 d_circ = 11"
  PYTHONPATH=. uv run python -m search.experiments.e014.gross_ext > "$OUT/gross_build.log" 2>&1 || { echo "FAIL build gross"; FAIL=1; }
  for k in X Z; do prove "gross_$k" "results/E-014-gross-dcirc11-proof/inst_$k.txt" 11; done
fi

[ "$FAIL" -eq 0 ] && echo "ALL PASS" || { echo "SOME CHECKS FAILED"; exit 1; }
