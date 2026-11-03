# 打工武器六维数据分析

当前版本以 `weapon_data_1110` 合并参数为输入，覆盖71把实际武器与136种有效动作，输出击杀能力、极限射程、涂地涂墙、墨水效率、清杂能力和射击硬直六项评分。

六维仍采用0.5–5.0分。63把普通武器的正式总分采用三工作量任务模型，映射到1–5分；最终展示分按C[1,2)、B[2,3)、A[3,4)、S[4,5)、S+5定档。8把熊武器保留原总分与等级，其模型候选仅用于分析。

- [完整分析与中文图表](../../docs/weapon-analysis.md)
- [V2方法与复算说明](v2/README.md)
- [六维分数](v2/scores.csv)
- [原始指标](v2/benchmarks.csv)
- [当前发布总分与等级](v2/overall_scores.csv)
- [任务模型、发布值与历史人工总分对照](v2/comparison.csv)

## 复算

在项目根目录安装数值计算和绘图依赖：

```powershell
python -m pip install -r analysis/weapon_evaluation/requirements.txt
python analysis/weapon_evaluation/v2/evaluate_v2.py
python analysis/weapon_evaluation/v2/validate_v2.py
python analysis/weapon_evaluation/v2/generate_figures_v2.py
```

需要将重算总分写入网页武器表时，使用 `evaluate_v2.py --write`。该选项只更新63把普通武器的 `rating.overall` 和 `rating.tier`；71把武器现有的426个六维值、8把熊武器与两条随机武器占位记录完整保留。六维字段保存0.5–5.0的数字，总分保存1–5的数字，均为高分更优。不带 `--write` 时只生成分析产物。

复算生成的 `v2/evaluation.json` 保存动作事件、共享墨量、任务排程与情景分解；该文件与报告排版产物不纳入Git。公开图表位于 `docs/images/weapon-analysis/`，重新绘图的输出位于本目录的 `v2/figures/`。

## 文件组织

`v2` 是当前评分与任务模型。上一级的 `evaluate.py`、`extract_common.py` 和 `extract_special.py` 提供参数读取、深合并及动作提取；`evaluation.json` 是V2读取的动作初始表，不代表当前网页评分。`notes/defaults_registry.json` 保存缺省参数来源，`v2/notes/endlag_measurements.json` 保存射击硬直的测量口径及资料链接。

V2直接读取已发布的初始动作表即可复算；无需运行初版评分写回。模型使用同水平熟练玩家的墙地同效条件，以五组生命值靶和固定混合敌群进行比较，再通过共享墨箱的连续任务模型分析六维相互作用。
