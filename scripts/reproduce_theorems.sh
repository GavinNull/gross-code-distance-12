#!/bin/bash
# 一键复现项目中经 auditor 复核的电路距离定理（auditor 2026-10-05 问题 2：证明须能由一条命令复现）。
#
#   bash scripts/reproduce_theorems.sh               # BB108、E-015 四个定理、IBM [[72,12,6]]（约 1 CPU 小时）
#   bash scripts/reproduce_theorems.sh --with-gross  # 另加 gross Fig. 12 d_circ = 11（W=10，约 4 CPU 小时）
#   可选（可与上面组合）：
#   --with-morphing         E-017 morphing [[144,12,12]] d_circ = 12（单轮实例 W=11 穷举 + W=12 阳性对照 +
#                           Prop. 1 折叠前提的计算核对，T=2..5，两基底）；E-019 全部 56 个小母码电路
#                           （[[72]]、[[108]]、[[144]] 母码，含 8 个 d_circ < d̃ 的）逐个核对精确值（约 0.8 CPU 小时）
#   --all-morphing          同上，另加 E-019 的 24 个 [[288]] 母码电路（约 14 CPU 小时；MORPH288_KEYS="bb288_x_sw11 ..." 可只跑部分）
#   --with-gross-retiming   E-020 P=8：auditor 的非 SAT C 回溯枚举合法起点赋值（固定 X0 应得 4 个，不固定应得 32 = 8×4），
#                           再对每个电路在 R=3 两基底各提升并注入一个权重 11 见证（评估器 verify_faults）（约 0.5 CPU 小时）
#   --with-gross12          E-021 gross [[144,12,12]] 交错电路 cand_p21（周期 21）d_circ = 12，任意 R、两基底：auditor 脚本
#                           查合法性与扩展码 = Fig. 12；E-018 审计的 w11dfs 从头重建权重 11 扩展码逻辑（W=11，按 24 元群展开，
#                           每侧应得 4224）；auditor 的 CP-SAT 精确 lift R=1..13 两基底应 0 提升、Fig. 12 R=1 阳性对照 4224/4224；
#                           权重 12 注入（上界）；任意 R 论证的前提（约 1.5 CPU 小时）
#   --skip-base             不跑默认的 BB108 / E-015 / IBM [[72]] 部分（只跑所选的可选部分）
#   环境变量：P = 并行进程数（默认 4，不超过 6）；OUT = 输出目录（默认 results/reproduce_theorems，须为仓库内相对路径）。
#
# 每个定理 d_circ = w 的检验方式（下界依据 Strikis 等 arXiv 2603.05481 Prop. 3；morphing 电路依据 Shaw–Terhal
# arXiv 2604.09797 Prop. 1 折叠到单轮实例，前提由 auditor 的 c3_rounds.py 计算核对）：
#   1) 实例上 W = w-1 的完整 DFS：全部轨道情形 found=0，且 SUMMARY 行数 = 作业数（防止崩溃被漏算）；
#   2) 阳性对照：W = w 时 DFS 能找到解（找到第一个即按 PID 停止）。
# E-019 由实验者流水线（search/experiments/e019）对每个电路给出精确值：W = d-1 穷举无解 + 见证注入全探测器电路。
# 上界（注入验证的权重 w 见证）对 BB108/E-015/gross 见各日志与审计报告，这里不重跑。
#
# 实验与审计脚本里写死的结果目录由 scripts/repro_redirect.py 在加载时改写到 $OUT 下（磁盘上的脚本不改），
# 所以本脚本不读取也不写入任何旧的 results/E-0xx 目录（默认部分与 --with-gross 的行为保持原样）。
set -u
cd "$(dirname "$0")/.."
P=${P:-4}
OUT=${OUT:-results/reproduce_theorems}
BASE=1; GROSS=0; MORPH=0; MORPH_ALL=0; RETIME=0; GROSS12=0
for a in "$@"; do
  case "$a" in
    --with-gross) GROSS=1 ;;
    --with-morphing) MORPH=1 ;;
    --all-morphing) MORPH=1; MORPH_ALL=1 ;;
    --with-gross-retiming) RETIME=1 ;;
    --with-gross12) GROSS12=1 ;;
    --skip-base) BASE=0 ;;
    *) echo "unknown option $a"; exit 2 ;;
  esac
done
mkdir -p "$OUT"
cc -O3 -o "$OUT/dfs128" search/experiments/e014/dfs128.c || exit 1
FAIL=0
RR="uv run python scripts/repro_redirect.py"

prove() {  # prove <name> <inst> <w> [dfs binary] [parts of case 0] [control case order]
  local name=$1 inst=$2 w=$3 bin=${4:-$OUT/dfs128} split0=${5:-1} ctrl=${6:-}
  local no; no=$(head -1 "$inst" | awk '{print $3}')
  local dir="$OUT/$name"; mkdir -p "$dir"
  local jobs  # 每行一个作业：<case> 或 <case> <split_mod> <split_idx>（case 0 拆成 split0 份，互不相交且完整）
  if [ "$split0" -gt 1 ]; then jobs=$( { for i in $(seq 0 $((split0 - 1))); do echo "0 $split0 $i"; done; seq 1 $((no - 1)); } )
  else jobs=$(seq 0 $((no - 1))); fi
  local njobs; njobs=$(echo "$jobs" | wc -l | tr -d ' ')
  echo "$jobs" | xargs -P "$P" -L 1 sh -c 'tag=c$4${6:+_s$6}; "$1" "$2" "$3" "$4" ${5:+$5} ${6:+$6} > "$0/W$3_$tag.txt"' \
    "$dir" "$bin" "$inst" $((w - 1))
  local nsum found
  nsum=$(cat "$dir"/W$((w - 1))_c*.txt | grep -c '^SUMMARY')
  found=$(cat "$dir"/W$((w - 1))_c*.txt | grep '^SUMMARY' | sed 's/.*found=\([0-9]*\).*/\1/' | paste -sd+ - | bc)
  local ctrl_ok=0 cf pid
  for c in ${ctrl:-$(seq 0 $((no - 1)))}; do
    # 找到第一个解即按 PID 停止（DFS 在打印 50 个解后会静默跑完整个情形，不能等它自然结束）
    cf="$dir/W${w}_control_c$c.txt"
    "$bin" "$inst" "$w" "$c" > "$cf" 2>&1 &
    pid=$!
    while kill -0 "$pid" 2>/dev/null && ! grep -q '^FOUND' "$cf"; do sleep 1; done
    kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null
    if grep -q '^FOUND' "$cf"; then ctrl_ok=1; break; fi
  done
  if [ "$nsum" -eq "$njobs" ] && [ "$found" -eq 0 ] && [ "$ctrl_ok" -eq 1 ]; then
    echo "PASS  $name: no logical of weight <= $((w - 1)) ($no orbit cases, $njobs jobs), weight-$w control found"
  else
    echo "FAIL  $name: summaries $nsum/$njobs, found(W=$((w - 1)))=$found, control(W=$w)=$ctrl_ok"; FAIL=1
  fi
}

to128() { awk 'NR==1{print; next} NF==3{print $1, 0, $2, $3; next} {print}' "$1" > "$2"; }

if [ "$BASE" -eq 1 ]; then
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
fi

if [ "$GROSS" -eq 1 ]; then
  echo "== E-014  gross Fig. 12 d_circ = 11"
  PYTHONPATH=. uv run python -m search.experiments.e014.gross_ext > "$OUT/gross_build.log" 2>&1 || { echo "FAIL build gross"; FAIL=1; }
  for k in X Z; do prove "gross_$k" "results/E-014-gross-dcirc11-proof/inst_$k.txt" 11; done
fi

if [ "$MORPH" -eq 1 ]; then
  M=$OUT/morph; mkdir -p "$M"
  echo "== E-017  Shaw–Terhal morphing [[144,12,12]]（f_x，仓库层序）d_circ = 12，任意轮数、两基底"
  S17=research/audits/2026-10-08-E-017-scripts
  ok=1
  for b in Z X; do for T in 2 3 4 5; do
    REPRO_MAP="results/E-017-audit=$M/e017_audit" $RR $S17/c2_instance.py x repo $b $T --stim-check >> "$M/e017_fold.log" 2>&1 &&
    REPRO_MAP="results/E-017-audit=$M/e017_audit" $RR $S17/c3_rounds.py x repo $b $T >> "$M/e017_fold.log" 2>&1 || ok=0
  done; done
  [ "$ok" -eq 1 ] || { echo "FAIL  e017 fold-check scripts crashed (see $M/e017_fold.log)"; FAIL=1; }
  uv run python scripts/repro_checks.py e017fold "$M/e017_audit" || FAIL=1
  cc -O3 -o "$M/dfsw" search/experiments/e017/dfsw.c || exit 1
  for b in Z X; do
    uv run python -m search.experiments.e017.dfs_inst --basis $b --out "$M/e017_inst_$b.txt" > "$M/e017_inst_$b.log" 2>&1 \
      || { echo "FAIL  build e017 instance $b"; FAIL=1; continue; }
    grep -q "'rows': 144, 'cols': 864, 'group_order': 72, 'orbits': 12" "$M/e017_inst_$b.log" \
      || { echo "FAIL  e017 instance $b: unexpected size/symmetry"; FAIL=1; }
    # case 0 拆成 4 份并行；阳性对照从最后一个情形往前试（后面的情形树小：Z 在 case 6、X 在 case 7 数秒内找到；case 0 在 W=12 上很慢）
    prove "e017_$b" "$M/e017_inst_$b.txt" 12 "$M/dfsw" 4 "$(seq 11 -1 0)"
  done

  D=$M/e019; mkdir -p "$D"
  RM19="results/E-019-morphing-family=$D"
  cc -O3 -o "$D/adfs" search/experiments/e019/adfs.c || exit 1
  if [ "$MORPH_ALL" -eq 1 ]; then
    echo "== E-019  Shaw–Terhal 两轮 morphing 电路族：56 个小母码电路 + 24 个 [[288]] 母码电路的精确 d_circ"
  else
    echo "== E-019  Shaw–Terhal 两轮 morphing 电路族：56 个小母码电路（[[72]]、[[108]]、[[144]] 母码）的精确 d_circ"
  fi
  REPRO_MAP=$RM19 $RR -m search.experiments.e019.construct > "$D/construct.log" 2>&1 || { echo "FAIL  e019 construct"; FAIL=1; }
  SMALL=$(uv run python -c "
from search.experiments.e019.common import variants
print(' '.join('_'.join(t) for t in variants() if t[0] != 'bb288'))")
  BIG=""
  if [ "$MORPH_ALL" -eq 1 ]; then
    BIG=${MORPH288_KEYS:-$(uv run python -c "
from search.experiments.e019.common import variants
print(' '.join('_'.join(t) for t in variants() if t[0] == 'bb288'))")}
  fi
  echo "   $(echo $SMALL | wc -w | tr -d ' ') small-parent circuits, $(echo $BIG | wc -w | tr -d ' ') [[288]] circuits"
  # xargs 把每行的参数接在固定参数之后：$0 = REPRO_MAP，$1 = 输出目录，$2 = key，$3 = 基底
  # 端点码距离（每个 key 一个进程）→ 实例（T=4，两基底；含 stim、局域、各轮等价、折叠条件、对称检查）→ 求解与注入
  for k in $SMALL $BIG; do echo "$k"; done | xargs -P "$P" -L 1 sh -c \
    'REPRO_MAP="$0" uv run python scripts/repro_redirect.py -m search.experiments.e019.endcycle "$2" > "$1/endcycle_$2.log" 2>&1' "$RM19" "$D"
  for k in $SMALL $BIG; do echo "$k Z"; echo "$k X"; done | xargs -P "$P" -L 1 sh -c \
    'REPRO_MAP="$0" uv run python scripts/repro_redirect.py -m search.experiments.e019.instance "$2" "$3" 4 > "$1/instance_$2_$3.log" 2>&1' "$RM19" "$D"
  for k in $SMALL; do echo "$k Z"; echo "$k X"; done | xargs -P "$P" -L 1 sh -c \
    'REPRO_MAP="$0" uv run python scripts/repro_redirect.py -m search.experiments.e019.solve "$2" "$3" --npar 1 > "$1/solve_$2_$3.log" 2>&1' "$RM19" "$D"
  for k in $BIG; do for b in Z X; do   # [[288]]：W = d̃-1 穷举（case 0/1 拆分，P 个线程）；上界由注入的端点码逻辑算子给出
    REPRO_MAP=$RM19 $RR -m search.experiments.e019.solve "$k" "$b" --npar "$P" --no_posctl > "$D/solve_${k}_$b.log" 2>&1
  done; done
  uv run python scripts/repro_checks.py e019 "$D" $SMALL $BIG || FAIL=1
fi

if [ "$RETIME" -eq 1 ]; then
  echo "== E-020  gross-dcirc 任务（max_period=8）保持 Fig. 12 每校验 CNOT 顺序、只改时序：P=8 全部合法电路都有权重 11 逻辑（R=3）"
  G=$OUT/retime; mkdir -p "$G"
  S20=research/audits/2026-10-09-E-020-scripts
  MAP20="results/E-020-audit=$G;results/E-020-gross-perchk-pipeline=$G;results/E-014-gross-dcirc11-proof=$G/e014"
  REPRO_MAP=$MAP20 PYTHONPATH=.:tests $RR $S20/b1_p8_instance.py > "$G/p8_instance.log" 2>&1 \
    && grep -q "reduction agrees with evaluator validate_schedule on 3000 vectors" "$G/p8_instance.log" \
    && echo "PASS  e020 reduction: per-check start s_c in Z_8 <=> evaluator validate_schedule (3000 vectors)" \
    || { echo "FAIL  e020 P=8 instance / reduction (see $G/p8_instance.log)"; FAIL=1; }
  cc -O3 -o "$G/p8search" $S20/p8search.c || exit 1
  "$G/p8search" "$G/p8_inst.txt" > "$G/p8search_all.txt" 2>&1 &     # 不固定：应得 32 = 8 个全局平移 × 4
  ALLPID=$!
  "$G/p8search" "$G/p8_inst.txt" 0 4 > "$G/p8search_fix0.txt" 2>&1    # 固定 X 校验 0 的起点 = 4（Fig. 12）
  n4=$(grep -c '^SOL' "$G/p8search_fix0.txt")
  if grep -q "^DONE solutions=4 " "$G/p8search_fix0.txt" && [ "$n4" -eq 4 ]; then
    echo "PASS  e020 p8search (X0 fixed): exactly 4 legal start assignments ($(grep DONE "$G/p8search_fix0.txt"))"
  else echo "FAIL  e020 p8search (X0 fixed): $n4 solutions, $(grep DONE "$G/p8search_fix0.txt")"; FAIL=1; fi
  REPRO_MAP=$MAP20 PYTHONPATH=.:tests $RR $S20/b3_p8_props.py > "$G/p8_props.log" 2>&1
  np=$(grep -c "colour-uniform True .*non-interleaved qubits 144 deterministic True" "$G/p8_props.log")
  [ "$np" -eq 4 ] && echo "PASS  e020 properties: all 4 colour-uniform, all 144 data qubits non-interleaved, deterministic (stim)" \
    || { echo "FAIL  e020 properties: $np/4 (see $G/p8_props.log)"; FAIL=1; }
  # 权重 11 扩展码逻辑：gross_ext 重建扩展码，W=11 DFS 找到第一个解即按 PID 停止
  REPRO_MAP=$MAP20 PYTHONPATH=. $RR -m search.experiments.e014.gross_ext > "$G/gross_build.log" 2>&1 || { echo "FAIL build gross ext"; FAIL=1; }
  for k in X Z; do
    cf="$G/w11_$k.txt"
    "$OUT/dfs128" "$G/e014/inst_$k.txt" 11 0 > "$cf" 2>&1 &
    pid=$!
    while kill -0 "$pid" 2>/dev/null && ! grep -q '^FOUND' "$cf"; do sleep 1; done
    kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null
  done
  REPRO_MAP=$MAP20 PYTHONPATH=.:tests $RR scripts/repro_retiming.py "$G" "$G/p8search_fix0.txt" "$G/w11_X.txt" "$G/w11_Z.txt" 3 \
    > "$G/lift.log" 2>&1
  grep -q "^RETIMING_LIFT OK" "$G/lift.log" \
    && echo "PASS  e020 lift: 4 distinct circuits (incl. Fig. 12), each R=3 basis Z and X has a weight-11 extended logical that lifts" \
    || { echo "FAIL  e020 lift (see $G/lift.log)"; FAIL=1; }
  # auditor 的注入脚本：评估器电路（sd6）+ 评估器 distance.verify_faults，要求 0 探测器、observable 翻转、11 个互异 DEM 列
  REPRO_MAP=$MAP20 PYTHONPATH=.:tests $RR $S20/b2_inject.py 3 1 > "$G/inject.log" 2>&1
  grep -q "^confirmed 8 / 8" "$G/inject.log" \
    && echo "PASS  e020 injection: 8/8 (4 circuits x 2 bases, R=3) weight-11 undetected logicals verified by the evaluator => d_circ <= 11" \
    || { echo "FAIL  e020 injection: $(tail -1 "$G/inject.log")"; FAIL=1; }
  wait "$ALLPID"
  grep -q "^DONE solutions=32 " "$G/p8search_all.txt" \
    && echo "PASS  e020 p8search (unfixed): 32 solutions = 8 global shifts x 4 ($(grep DONE "$G/p8search_all.txt"))" \
    || { echo "FAIL  e020 p8search (unfixed): $(grep DONE "$G/p8search_all.txt")"; FAIL=1; }
fi

if [ "$GROSS12" -eq 1 ]; then
  echo "== E-021  gross [[144,12,12]] 单辅助比特交错电路 cand_p21（周期 21）d_circ = 12，任意 R、两基底（auditor 脚本，不调用 e021 代码）"
  Q=$OUT/gross12; mkdir -p "$Q"
  S21=research/audits/2026-10-10-E-021-scripts; S18=research/audits/2026-10-08-E-018-scripts
  # 审计脚本写死的 results/E-021-audit（输出）、results/E-018-audit（扩展码实例与 W=11 DFS 输出）改写到 $Q 下
  export SPEC=search/experiments/e021/cand_p21_spec.json
  MAP21="results/E-021-audit=$Q/audit;results/E-018-audit=$Q/e018"
  R21="env -u TAG REPRO_MAP=$MAP21 PYTHONPATH=.:tests $RR"
  $R21 $S21/b1_legal.py > "$Q/b1_legal.log" 2>&1 || { echo "FAIL  e021 b1_legal crashed (see $Q/b1_legal.log)"; FAIL=1; }
  $R21 $S21/b2_ext.py 3 > "$Q/b2_ext.log" 2>&1 || { echo "FAIL  e021 b2_ext crashed (see $Q/b2_ext.log)"; FAIL=1; }
  # 权重 11 扩展码逻辑从头重建：E-018 审计的扩展码实例 + 列轨道类任务（每类 8 份）+ w11dfs（W=11），按 24 元群展开
  $R21 $S18/a2_stage_a.py prep > "$Q/e018_prep.log" 2>&1 && $R21 scripts/repro_gross12.py jobs >> "$Q/e018_prep.log" 2>&1 \
    || { echo "FAIL  e021 W=11 instance / jobs (see $Q/e018_prep.log)"; FAIL=1; }
  cc -O3 -o "$Q/e018/w11dfs" $S18/w11dfs.c || exit 1
  ( cd "$Q/e018" && xargs -P "$P" -L 1 sh -c 'EXCL=$4 ./w11dfs inst_$0.txt 11 $1 $2 $3 > dfs_$0_$1_$3.txt' < jobs.txt 2> dfs.log )
  $R21 scripts/repro_gross12.py list > "$Q/list.log" 2>&1 || FAIL=1
  grep -E '^(PASS|FAIL)' "$Q/list.log" || { echo "FAIL  e021 weight-11 list (see $Q/list.log)"; FAIL=1; }
  # 精确 lift（auditor 的 CP-SAT b3）：候选 R=1..13 两基底（任意 R 论证需要 R <= 13）；阳性对照 Fig. 12 R=1 两基底
  # （每行不能以空格结尾：BSD xargs -L 会把下一行接上来）
  { echo "cand Z" $(seq 1 13); echo "cand X" $(seq 1 13); echo "fig12 Z 1"; echo "fig12 X 1"; } | xargs -P "$P" -L 1 sh -c \
    'r=$0 s=$1 q=$2; shift 2; $r $s/b3_lift.py "$@" > "$q/b3_$1_$2.log" 2>&1' "$R21" "$S21" "$Q"
  $R21 $S21/b6_inject.py > "$Q/b6_inject.log" 2>&1 || { echo "FAIL  e021 b6_inject crashed (see $Q/b6_inject.log)"; FAIL=1; }
  $R21 $S21/b7_periodic.py > "$Q/b7_periodic.log" 2>&1 || { echo "FAIL  e021 b7_periodic crashed (see $Q/b7_periodic.log)"; FAIL=1; }
  $R21 scripts/repro_gross12.py check 13 || FAIL=1
  unset SPEC
fi

[ "$FAIL" -eq 0 ] && echo "ALL PASS" || { echo "SOME CHECKS FAILED"; exit 1; }
