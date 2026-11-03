# 打工武器六维评估与任务耦合模型

本版本采用统一的六维定义，以同水平熟练玩家作为操作条件。主武器参数来自项目的 `weapon_data_1110` 合并快照；敌方生命值使用三代 Salmon Run Next Wave 数据核对。10.0.1版本的指标定义与本地1110参数快照分别记录。完整分析见[武器数据分析](../../../docs/weapon-analysis.md)。

## 指标定义

| 字段 | 计算对象 | 原始量方向 |
| --- | --- | --- |
| Killing | 300、500、600盾加500本体、900、1200血五项生命值靶完成帧之和 | 越小越好 |
| Mob Clearing | 2只400血、3只100血、3只40血的混合群清除帧 | 越小越好 |
| Range | 平地不起跳条件下的最远命中距离计算值 | 越大越好 |
| Inking | 单位时间覆盖面积；按统一熟练度条件将墙涂与地涂设为一致 | 越大越好 |
| Ink Efficiency | 一箱墨在已建模固定动作中可造成的最大伤害，排除碾压 | 越大越好 |
| Endlag | 从射出到开始潜墨的最短时间，分别记录实测时钟、取消相位及参数近似 | 越小越好 |

展示分数统一为0.5–5.0，高分表示性能更有利。普通武器的对数第5和95百分位确定评分锚点，熊武器沿用该尺度。

每个生命值靶从满墨、未蓄力状态起步。600与500分阶段结算，前一阶段过量伤害丢弃；后续独立伤害事件可进入下一阶段。程序枚举完整固定动作，不在两种姿态之间免费转换。混合群中央场景使用2列4行点阵，同时输出分散与聚集情景。

射程计算区分自然爆点中心、伤害外边缘及涂墨半径。滚筒衰减末端、浴缸首次落地等不完整参数保留对应方法标记。射击硬直主要参考日本逐帧实测表，缺测熊武器分别保留参数近似与无弹丸攻击的扩展口径。

## 任务间的资源耦合

总体比较包含均衡、战斗偏重、环境维护偏重三类工作量。每类工作量按顺序执行生命值靶、混合群、涂地和涂墙任务。各任务使用实际选中的动作，计入首发准备、完整批次、发射间隔和退出窗口；墨箱余量跨任务传递，无法支付下一次原子动作时补墨。

接敌时间使用该任务实际动作的可达距离。近身刀身伤害不会借用远程刀波射程；翻滚动作不会借用普通站立射击的收招时间。涂墨使用离散覆盖包累计面积，蓄力武器的涂墨任务不会在第一发之前完成。

三个工作量情景分别定标，再取其分数均值形成候选总分。场景内的作用关系通过时间和共享墨量体现，不以六个雷达分数的简单加权替代。原`overall`和`tier`保留用于对照，候选总分、情景范围与名次范围输出到`comparison.csv`。原视频未给出的权重和额外事件加减分不进入本模型。

默认墙地同效；另对爆破枪测试0.6、0.8、1.0的涂墨折扣。队形、箭束汇聚、补墨时长和任务工作量的变化单独输出，便于检查结论对实验条件的依赖。

## 复算

在项目根目录安装`analysis/weapon_evaluation/requirements.txt`中的依赖后运行。已在conda base环境的NumPy 2.1.3与Matplotlib 3.10.0下验证：

```powershell
python analysis/weapon_evaluation/v2/evaluate_v2.py
python analysis/weapon_evaluation/v2/validate_v2.py
python analysis/weapon_evaluation/v2/generate_figures_v2.py
```

添加`--write`仅更新71把武器的六维字段。`weapon_data.before_v2.json`保存本轮前的武器表；上一级`evaluation.json`提供动作初始表。

## 结果文件

- `scores.csv`：71把武器六维分数。
- `comparison.csv`：新旧击杀分、候选总分、场景范围及方法来源状态。
- `benchmarks.csv`：五类生命值靶、三种杂鱼排列、整箱伤害和射击硬直的原始指标。
- `evaluation.json`：复算生成的全部动作、事件排程、墨量账本、情景分解及图表数据；不随仓库上传。
- `notes/endlag_measurements.json`：逐武器硬直测量与时钟定义。
- `notes/blaster_wall_profiles_method.json`：爆点与提前撞墙的参数诊断，作为机制资料保留，不改变默认墙地同效设置。
- `figures`：绘图脚本生成的中文图表；公开文档使用的图片位于`docs/images/weapon-analysis/`。

## 资料

1. [三代敌人与武器数据](https://splatoonwiki.org/wiki/Salmon_Run_Next_Wave_data)。
2. [前作数据入口](https://splatoonwiki.org/wiki/Salmon_Run_data)，其页首明确指向三代资料。
3. [日本前隙与后隙逐帧测量](https://wikiwiki.jp/splatoon3mix/検証/メインウェポン/前隙・後隙)。
4. [日本主武器参数研究](https://wikiwiki.jp/splatoon3mix/検証/パラメータ情報/メイン)。
5. [参数默认值说明](https://splatoonwiki.org/wiki/User:XarrotD/paramtable)。
6. [1110原始参数仓库](https://github.com/Leanny/splat3/tree/main/data/parameter/1110/weapon)。
