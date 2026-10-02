# E-001 / E-001b · 旋转表面码 baseline

- 日期：2026-10-02 / git commit：a9ab0cc（运行时；baselines/surface.py 与 yaml 在本次提交中更新）/ 评估器哈希：未冻结（P0）
- 假设：baseline（验证流水线）
- 问题：stim + sinter + pymatching 流水线能否复现旋转表面码的标准阈值行为？
- 复现命令：
  ```bash
  uv run python -m baselines.surface --config experiments/E-001-surface-baseline.yaml
  uv run python -m baselines.surface --config experiments/E-001b-surface-threshold.yaml
  ```
- 噪声模型：`stim.Circuit.generated("surface_code:rotated_memory_z")`，四个参数
  `after_clifford_depolarization` / `before_round_data_depolarization` /
  `before_measure_flip_probability` / `after_reset_flip_probability` 全部取 p。
  **注意：这个模型没有对空闲比特单独加噪声**，与 SD6 / SI1000 不同。
- 每轮错误率换算：`p_round = (1 - (1 - 2·p_shot)^(1/rounds)) / 2`，rounds = d。

## 事先预测
- E-001：交叉点 p≈0.6%~0.8%；p=1e-3 时 Λ（d 每 +2 的错误率下降倍数）约 5~8。
- E-001b（E-001 之后写）：交叉点在 1.0%~1.5% 之间。

## 结果

每轮逻辑错误率（95% 似然区间见 `results/*/summary.json`），E-001 每点 ≥200 次错误，E-001b 每点 ≥1000 次错误。

| p | d=3 | d=5 | d=7 |
|---|---|---|---|
| 0.001 | 2.83e-4 | 2.53e-5 | 2.48e-6 |
| 0.002 | 9.84e-4 | 1.94e-4 | 3.83e-5 |
| 0.003 | 2.23e-3 | 7.36e-4 | 2.13e-4 |
| 0.005 | 5.47e-3 | 2.91e-3 | 1.46e-3 |
| 0.008 | 1.41e-2 | 1.08e-2 | 6.61e-3 |
| 0.010（E-001b） | 2.11e-2 | 1.83e-2 | 1.60e-2 |
| 0.011 | 2.47e-2 | 2.15e-2 | 2.10e-2 |
| 0.012 | 2.96e-2 | 2.88e-2 | 2.82e-2 |
| 0.013 | 3.09e-2 | 3.32e-2 | 3.68e-2 |
| 0.015 | 3.98e-2 | 5.00e-2 | 5.23e-2 |

Λ（p=1e-3）：d3→d5 = 11.2，d5→d7 = 10.2。
图：`results/E-001-surface-baseline/threshold.png`。总耗时：E-001 约 7 秒，E-001b 约 1 分钟（4 核）。

## 与预测对比
- **E-001 两条预测均未命中。** 实测交叉点约 1.2%（不是 0.7%），Λ≈10（不是 5~8）。
  两处偏差方向一致且相互自洽：Λ ≈ p_th / p ≈ 0.012 / 0.001 ≈ 10。
  原因判断：0.7% 是我凭记忆取的、含空闲噪声的电路级模型（SD6 类）下的阈值，与本实验所用 stim 生成电路的噪声口径不同。
  这是预测的参照系错误，不是流水线错误。**未核实**：该噪声模型下的文献阈值，待 lit-scout 补充。
- E-001b 预测命中（交叉点约 1.2%，在 1.0%~1.5% 内）。

## 异常与疑点
- **流程违规（已修正）**：E-001b 的 yaml 写停止条件为 200 次错误，但代码里硬编码成了 1000，实际按 1000 运行。
  已改为代码从 yaml 读取 `max_errors`，yaml 改为实际运行值并加注释。多收错误只提高精度，不影响结论，但违反了“配置即真相”。
- d=3 在 p=0.012→0.013 几乎持平（2.96e-2 → 3.09e-2），在统计误差内，不视为异常。
- 结果本身没有“好得不像真的”的迹象。

## 结论
流水线可用：指数压制清晰，阈值行为自洽。**最重要的教训：噪声模型必须钉死并写进评估器。**
gross code 对比要使用与 IBM 论文完全相同的噪声口径，否则数字不可比。
本实验是 baseline，不声称改进，不需要 auditor 复核；G0 前会连同 E-002 一并请 auditor 复现。
