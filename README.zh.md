# Omicverse-RebuildR

**一套固定、可复现的协议，用于把 R / Bioconductor 包重构为纯 Python `py-<pkg>` 独立包，并提供加密级精度的数值一致性证明。**

🇬🇧 **English version**: [README.md](README.md)

---

## 这是什么

单细胞基因组学、统计遗传学、蛋白质组学及相关领域有数百个经典算法**只存在于 R / Bioconductor**：TSCAN、tradeSeq、Slingshot、DESeq2、edgeR、mclust、miloR、DoubletFinder、WGCNA、gsMap、condiments…

Python 用户需要这些算法时，目前的选项都不理想：

1. **通过 rpy2 / reticulate 调 R** — 需要装 R、序列化开销、GPU runtime 碎片化；agent workflow 极不友好。
2. **使用"差不多"的 Python 替代品** — 静默地变成另一个算法，统计行为不同。
3. **手动重写** — 专家工作量数周到数月；通常结果偏离 R 但偏离量没被量化。

Omicverse-RebuildR 是一套**工程菜谱**，把"我想要 Python 里有这个"变成"wheel 已发到 PyPI 并可证明在 canonical fixture 上与 R 完全一致" — 全程靠少量 agent-driven 迭代，并把一致性证据和 wheel 一起发出去。

三个核心思想：

1. **R 源码就是可执行规范。** 不从论文里逆向工程。Agent 把 R reference 跑在固定输入上，并把自己的草稿和这个输出每轮迭代对比一次。
2. **一致性是分类感知的。** 对于一个 embedding（旋转不变），一个 clustering（标签排列不变），或一个 pseudotime（相关系数不变），"输出相同"的定义不一样。协议在写任何 agent 代码之前就预先注册哪个数值度量适用于哪个输出，并把阈值锁死。
3. **重构不是 metric 优化。** 我们绝不调算法让它"看起来更好" — 我们调它让它与 R **完全相同**，然后在可证等价的代数重写下搜索速度提升。

每个 port 最终交付：

- PyPI 上 pip-installable 的 wheel。
- `RECONSTRUCTION_REPORT.md`：完整 R 函数覆盖率审计 / per-output parity 数值 / 双图 time-vs-accuracy / 生态复用账目。
- 三本 pre-executed notebook：pipeline parity、Python tutorial、R⇄Python 函数字典。
- 可复现的 parity gate（pytest 测试形式）。

---

## 快速开始

```bash
# 1. clone kit
git clone <your-repo-url> omicverse-rebuildr
cd omicverse-rebuildr

# 2. 准备 Python + R 两个 conda 环境（完整说明见 SETUP.md）
conda create -n rebuild-py python=3.10 -y
conda activate rebuild-py
pip install -r requirements.txt

conda create -n rebuild-r -c conda-forge r-base=4.3 r-essentials -y

# 3. 导出两个 kit 需要的路径
export PYTHON_TEST_ENV=$(conda info --envs | awk '/rebuild-py/ {print $NF}')
export R_TEST_ENV=$(conda info --envs | awk '/rebuild-r/ {print $NF}')

# 4. 登录 GitHub CLI（Discovery 阶段需要）
gh auth login

# 5. 30 秒确认 kit 安装干净
python -m engine.smoke_test
# 应输出：[smoke] OK -- 5/5 checks passed.

# 6. 检查目标 R 包是否已经被人重构过
python -m engine.discover_omicverse_deps --check <YourRPackage>
```

如果 smoke test 通过且 discovery 返回 "no existing port"，就可以开始重构了 — 参考 [PROTOCOL.md](PROTOCOL.md)。

📖 **完整安装步骤**：[SETUP.md](SETUP.md)（含 conda 环境配置，约 30 分钟）。

---

## 在 session 里怎么调用协议

把 agent（Claude Code、Cursor 等）指向这个文件夹，说：

```
重构 R 包 X。流程参考 omicverse-rebuildr/README.md
```

Agent 会端到端执行 6 步协议，最终产出：

- 一个 `omicverse/py-X` repo（或在你的 `$REBUILDR_ORG` 下）+ 可安装 wheel，
- 预注册的数值 parity gate 在 canonical fixture 上通过，
- 结构化的 `RECONSTRUCTION_REPORT.md`，
- 3 本必交的 pre-executed notebook（pipeline parity、Python tutorial、R⇄Python 函数字典），
- PyPI release。

---

## 协议 — 6 步

```
┌─ 0.5 Discovery ──────┐
│ • 目标是否已被重构？  │ ← 是 → 停止，复用现有 repo
│ • 哪些 R 依赖已有     │
│   py- 镜像？          │ ← 匹配的加进 pyproject.toml 作为
└──────────────────────┘   hard / optional dep
         ↓
┌─ 1 复制 shape 模板 ──┐
│ 从同算法类的现有 port │
│ 复制目录布局         │
└──────────────────────┘
         ↓
┌─ 2 双环境 ──────────┐
│ Python target env   │
│ R reference env     │
│ 两者看到同一份数据  │
└─────────────────────┘
         ↓
┌─ 3 双 agent 内环 ────────────────────────────────────────────────────┐
│                                                                       │
│  ┌─ Equivalence Agent ──┐    ┌─ Acceleration Agent ────────────────┐ │
│  │ 翻译 R → Python      │ →  │ 在代数重写空间里搜索速度提升        │ │
│  │ 迭代到 parity gate   │    │ 每个重写必须有 admissibility 证明：  │ │
│  │ 通过（Pearson、ARI、 │    │ exact / bounded-ε / class-          │ │
│  │ Procrustes 等）       │    │ containment。破坏 parity 即回滚。   │ │
│  └──────────────────────┘    └────────────────────────────────────┘ │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
         ↓
┌─ 4 验证 ────────────┐
│ 重新确认 gate。     │
│ 阈值只读，绝不放宽。│
└─────────────────────┘
         ↓
┌─ 5 发布 ────────────┐
│ 推到 PyPI + GitHub。│
│ 成为下一个 port 的  │
│ seed template。     │
└─────────────────────┘
```

每一步都有专门文档：

| 步骤 | 做什么 | 文档 |
|---|---|---|
| **0.5 Discovery** | 检查目标是否已经被重构；检查每个 R 依赖是否在 `github.com/<org>` 下有 py-镜像。已存在 → 停止；找到的依赖加进 `pyproject.toml`。 | [DISCOVERY.md](DISCOVERY.md) |
| **1 Shape 模板** | 从同算法类的 port 复制目录布局 + test 脚手架（例如 classification 用 `py-DoubletFinder`，ordinal 用 `py-monocle2`）。**不要**复制算法代码。 | [TEMPLATE.md](TEMPLATE.md) |
| **2 双环境** | 配 Python target env（Python + in-progress port）和 R reference env（R 4.x + Bioconductor + 上游 R 包）。两者共享同一份 fixture 文件。 | [SETUP.md](SETUP.md) |
| **3 双 agent 内环** | (a) **Equivalence Agent**：翻译 R → Python，迭代直到预注册的 class-aware parity gate 通过。(b) **Acceleration Agent**：verifier-guided test-time search，搜代数重写换速度，每个都要带三选一的 admissibility 证明。 | [PROTOCOL.md](PROTOCOL.md), [PARITY_TAXONOMY.md](PARITY_TAXONOMY.md), [ACCELERATION_PLAYBOOK.md](ACCELERATION_PLAYBOOK.md) |
| **4 验证** | 重新确认 gate。阈值在 agent 工作开始之前就锁死了，绝不在过程中收紧或放宽。 | [PARITY_TAXONOMY.md](PARITY_TAXONOMY.md) |
| **5 发布** | wheel 推到 PyPI，repo 推到 `github.com/<org>/py-X`，完成结构化的 `RECONSTRUCTION_REPORT.md` + 3 本必交 notebook。该 port 成为未来 port 的候选 seed template。 | [NOTEBOOKS.md](NOTEBOOKS.md) |

---

## 8 个算法分类（parity taxonomy）

不同算法有不同的不变性结构，所以"输出相同"需要不同的度量。协议为每个 port 输出预注册一个分类：

| # | 分类 | 一致性度量 | 默认阈值 | 例子 R 包 |
|---|---|---|---|---|
| 1 | **Deterministic numerical** | 元素级 `max_abs_err < tol` AND Pearson = 1 | `tol = 1e-13` (f64) | BandNorm, scHiCluster kernels |
| 2 | **Stochastic numerical** | Kolmogorov–Smirnov ≤ τ 或 Wasserstein-1 ≤ τ | KS-p ≥ 0.05 | MCMC 抽样、贝叶斯后验 |
| 3 | **Combinatorial clustering** | 标签不变：ARI / NMI / Fowlkes–Mallows | ARI ≥ 0.95 | mclust, scDblFinder, sc3 |
| 4 | **Continuous embedding** | 旋转不变：Procrustes similarity | Procrustes ≥ 0.95 | Seurat CCA, PCA, UMAP, t-SNE |
| 5 | **Ranked output** | top-K Jaccard / Spearman 相关 | top-50 Jaccard ≥ 0.8 | COSG markers, DE 排名 |
| 6 | **Ordinal output (pseudotime)** | Pearson / Spearman 相关 | Pearson ≥ 0.99 | Monocle 2, Slingshot, TSCAN |
| 7 | **Classification** | 标签一致 / F1 | F1 ≥ 0.95 | DoubletFinder, scDblFinder labels |
| 8 | **Statistical inference** | rank corr on −log10 p + top-K Jaccard | Spearman ≥ 0.90 | miloR DA, limma, DESeq2, tradeSeq |

如果 R 函数返回多个不同分类的输出，manifest 为每个输出声明一个 gate，**全部必须通过**。

8 个度量的实现都在 [`engine/parity_metrics.py`](engine/parity_metrics.py) 里 — 直接 import，不要重新定义。

📖 完整分类细节：[PARITY_TAXONOMY.md](PARITY_TAXONOMY.md)，含"gate 失败时的怀疑列表"（off-by-one、转置、log 底数、稀疏 vs 稠密、NA 处理…）。

---

## Acceleration：3 类 admissibility 证明

Acceleration Agent 提交的每一个代数重写都必须带下面其中一种证明：

| 证明类 | 含义 | 例子 |
|---|---|---|
| **(E) Exact identity** | 重写在数学恒等式下产生 bit-equivalent 输出。 | `X^T X` 缓存到循环外；Woodbury `(I + λ U Λ U^T)^{-1}`；Schur complement；Cholesky vs LU。 |
| **(B) Bounded ε-approximation** | 重写引入的误差有闭式上界；上界要在 `MATH.md` 推导，不能口嗨。 | 稀疏 soft-assignment 在 ε = 1e-12 行截断（带 `‖W_new − W‖_F ≤ κ n K ε`）；下游为局部时 top-K kNN 截断成对距离矩阵。 |
| **(C) Class-containment 定理** | 已有定理保证重写在相关输入类上产生相同输出。 | 欧氏 MST ⊆ Delaunay 三角化（Preparata-Shamos 1985, Toussaint 1980）；MST ⊆ relative-neighbourhood graph。 |

📖 完整目录：[ACCELERATION_PLAYBOOK.md](ACCELERATION_PLAYBOOK.md)。Acceleration Agent 按启发式顺序搜，被拒绝的重写也要记到 `ITERATION_LOG.md`。

---

## 评估：两图，不是一图

传统进化搜索画 `iteration vs metric`，因为 policy 在搜*更好的 metric*。**这套这里是错的模型** — 重构的目标是与 R reference **完全相同**的输出，不是"更好"的输出。

所以每个 port 产生两张图，共享同一条 iteration 横轴：

```
 wall-clock (s)
  │
  │  ●─┐
  │    │  ●─┐
  │       │    ●──●
  │ baseline → iter 1 → iter 2 → iter 3 → iter 4
  │
  └──────────────────────────────────────────────→ iteration

 parity 度量（如 Pearson）
  │ ●──●──●──●─┐
  │              \
  │               ●──●   ← 标注："row truncation at ε=1e-12"
  │  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ 阈值（红色虚线）
  │
  └──────────────────────────────────────────────→ iteration
```

- **图 1（上，log 轴）**：墙钟时间在重写被接受时单调下降。误差棒 = 3 次去热启动后的 stddev。
- **图 2（下）**：parity 度量应平在天花板。每个凹点都必须标注是哪个数学近似导致的。

墙钟测量规则：
- **热启动**：丢掉第一次（BLAS 线程池预热、Python imports、page cache）。
- **3 次测量**在同一进程里跑；报告 mean ± stddev。
- **CV > 10% → 自动延长到 5 次**，报告 median + IQR。
- **固定 BLAS 线程数**：`OMP_NUM_THREADS=8` 等，在 import 之前设。

📖 完整规范 + iteration log schema：[EVALUATION.md](EVALUATION.md)。

---

## 每个 release 必交 3 本 notebook

一个完成的 port 服务**四类受众**，每类需求不同：

| 受众 | 需要什么 | 看哪里 |
|---|---|---|
| **评审 / 科学家**评估能否信任这个 port | pipeline 级证明 Python ≡ R 数值 | [`compare_R_vs_Python.ipynb`](templates/compare_R_vs_Python.template.ipynb) |
| **新用户**第一次接触这个算法 | 每个公开函数的 Python 走读 | [`tutorial_<dataset>.ipynb`](templates/tutorial.template.ipynb) |
| **R 用户**把现有 R 代码逐行迁移到 Python | 函数级字典 — 每个 R 参数 ↔ Python 参数，同一输入下并排调用 | [`function_by_function_R_parity.ipynb`](templates/function_by_function_R_parity.template.ipynb) |
| **CI / 自动化** | 预注册的 parity gate（pytest 断言） | `tests/test_exact_match.py` |

三本 notebook 都**预先执行**并提交输出，GitHub 上能直接预览。协议 Phase 4 阶段任何一本缺失都会卡住 release。

📖 schema + section-by-section 要求：[NOTEBOOKS.md](NOTEBOOKS.md)。

---

## Kit 内容

### 顶层文档

| 文件 | 作用 |
|---|---|
| [SETUP.md](SETUP.md) | **第一次安装** — 前置依赖、双环境配置、env vars、gh auth、smoke test、排错。 |
| [PROTOCOL.md](PROTOCOL.md) | **6 步协议**正文 + 双 agent 内环。Session 开始前读这个。 |
| [DISCOVERY.md](DISCOVERY.md) | Phase 0.5 — 复用先于重建。查目标和它的 R 依赖在 org 下有没有 py-镜像。 |
| [PARITY_TAXONOMY.md](PARITY_TAXONOMY.md) | 8 类算法 → 哪个数值 parity 度量适用。 |
| [ACCELERATION_PLAYBOOK.md](ACCELERATION_PLAYBOOK.md) | 代数重写目录，3 类 admissibility 证明。 |
| [EVALUATION.md](EVALUATION.md) | 双图评估（`time vs iter` + `accuracy vs iter`），去热启动，accuracy 凹点标注。 |
| [NOTEBOOKS.md](NOTEBOOKS.md) | 每个 release **3 本必交** pre-executed notebook。Phase 4 不可跳过。 |
| [TEMPLATE.md](TEMPLATE.md) | 标准 `py-<pkg>` repo 布局 + 命名规范 + license 决策表。 |
| [CHECKLIST.md](CHECKLIST.md) | per-port checklist，Phase 0–5。 |

### Engine（可运行代码）— `engine/`

| 文件 | 作用 | 典型调用 |
|---|---|---|
| `smoke_test.py` | 30 秒 sanity check — kit 是否装好、8 个 parity metric + audit/plot/benchmark/loop helper 是否能跑。 | `python -m engine.smoke_test` |
| `discover_omicverse_deps.py` | 通过 `gh repo list <org>` 列已有 org repo（默认 `omicverse`，可用 `REBUILDR_ORG` env var 覆盖）；解析 R `DESCRIPTION`；报告哪些依赖已有 py-镜像。24h 缓存。 | `python -m engine.discover_omicverse_deps --check <RPkg>` |
| `parity_metrics.py` | 8 类 parity 度量函数（Pearson、ARI、Procrustes、KS、top-K Jaccard…）+ 类分发器。 | `from parity_metrics import compute_parity, is_pass` |
| `benchmark.py` | 墙钟计时器，去热启动 + 3 次取平均；CV > 10% 自动延到 5 次取中位。 | `from benchmark import time_callable` |
| `r_function_audit.py` | 解析 R `NAMESPACE` + `R/*.R`，审计 Python 覆盖率，产出 `AUDIT.md`。 | `python -m engine.r_function_audit --r-source <pkg>-ref --py-package <pkg>` |
| `plot_evolution.py` | 从 `ITERATION_LOG.md` 渲染双图 PNG，accuracy 凹点处自动标数学原因。 | `python -m engine.plot_evolution --port-dir <path>` |
| `loop.py` | Omicverse-RebuildR 循环的 runnable 形式 — equivalence + acceleration phase 作为 Python callable。 | `python -m engine.loop --port-dir <path> --phase equivalence` |
| `manifest.template.yaml` | 预注册 parity gate 规范 — 拷到每个新 port 的 `data/manifest.yaml`。 | （文件模板） |

### 文件级模板 — `templates/`

每个新 port 直接拷这些做起点，没有任何东西从零生成。

| 模板 | 拷出来成为 |
|---|---|
| `pyproject.template.toml` | port 的 `pyproject.toml`（build + deps + metadata） |
| `README.template.md` | port 的用户向 `README.md` |
| `r_reference_driver.template.R` | `tests/r_reference_driver.R` — 调 R 包，dump JSON |
| `_run_candidate.template.py` | `tests/_run_candidate.py` — 调 Python port，dump JSON |
| `test_exact_match.template.py` | `tests/test_exact_match.py` — pytest 断言 gate |
| `DISCOVERY.template.md` | port 的 `DISCOVERY.md` artefact（Phase 0.5） |
| `ITERATION_LOG.template.md` | port 的 `ITERATION_LOG.md`（Phase 3 acceleration log） |
| `RECONSTRUCTION_REPORT.template.md` | port 的 `RECONSTRUCTION_REPORT.md`（8 节最终报告） |
| `compare_R_vs_Python.template.ipynb` | Notebook 1 — pipeline parity |
| `tutorial.template.ipynb` | Notebook 2 — Python tutorial |
| `function_by_function_R_parity.template.ipynb` | Notebook 3 — R⇄Python 函数字典 |
| `r_per_function_dump.template.R` | 给 Notebook 3 用的 R driver |

### 示例 & 路线图 — `examples/`

| 文件 | 作用 |
|---|---|
| [ROADMAP_TRAJ.md](examples/ROADMAP_TRAJ.md) | trajectory inference R 包候选列表（TSCAN ✅、tradeSeq、destiny、URD、SCORPIUS、condiments…），含引用数 + cites/year。 |
| [EXAMPLE_WALKTHROUGH.md](examples/EXAMPLE_WALKTHROUGH.md) | TSCAN 端到端走读 — Phase 0 → Phase 5 叙述，含具体命令和中间产出。 |

---

## Agent 在一个 session 里做什么

典型 session 开场：

```
重构 R 包 X。流程参考 omicverse-rebuildr/README.md
```

Agent 然后执行：

1. **（Phase 0.5 — Discovery）**跑 `engine/discover_omicverse_deps.py` 检查：
   - `omicverse/py-X`（或 `<your-org>/py-X`）是否已经发过？→ 是 → **停止**，报告现有 repo。
   - X 的哪些 R 依赖已有 py-镜像？→ 匹配项记到 `DISCOVERY.md`，加进 `pyproject.toml`。
2. **（Phase 0）**在 `PARITY_TAXONOMY.md` 里查 X 的算法分类。写 `data/manifest.yaml`（含算法分类、阈值、canonical fixture 路径、seed、per-output gate block）并提交。**Gate 此后只读。**
3. **（Phase 1）**从 `TEMPLATE.md` 复制布局（seed shape 由算法分类决定 — 比如 ordinal trajectory 用 `py-monocle2`）。
4. **（Phase 2 — Equivalence Agent）**按依赖顺序翻译每个 R 函数。每个函数后跑 per-function parity diff。迭代到顶层 gate 在预注册阈值下通过。
5. **（Phase 3 — Acceleration Agent）**对 `ACCELERATION_PLAYBOOK.md` 里每个候选重写：
   - 检查 precondition + 产出 admissibility 证明（E / B / C）。
   - 在工作分支上 apply；重跑 parity test（gate 还过吗？）；重 benchmark。
   - 加速 > 1.05× 且 gate 过 → 接受；否则回滚。
   - 每次尝试在 `ITERATION_LOG.md` 添加一段 YAML block。
6. **（Phase 4 — release artefacts）**完整勾过 `CHECKLIST.md`；产出所有必交物：
   - `RECONSTRUCTION_REPORT.md`（8 节，从每阶段产物填）
   - `MATH.md`（任何 (B) 重写的扰动上界）
   - `AUDIT.md`（R 函数覆盖率，`engine.r_function_audit` 自动生成）
   - `examples/evolution.png`（双图 time + accuracy，`engine.plot_evolution` 自动生成）
   - **`examples/compare_R_vs_Python.ipynb`** — pipeline parity
   - **`examples/tutorial_<dataset>.ipynb`** — Python-only 函数教程
   - **`examples/function_by_function_R_parity.ipynb`** — R⇄Python 函数字典
7. **（Phase 5 — release）**构建 wheel，推 PyPI；建 GitHub repo + release；把 port 加进 seed template 列表。

**Always-first invariant**：Phase 0.5（Discovery）不可跳过。跳了协议就失败 — 会重复实现已存在的上游。TSCAN port 靠中途发现 `py-mclustR` 省了约 3000 行 Mclust 代码；下个 port 应该在 Step 1 就拿到这种节省，不是靠运气。

**Phase 4 无 deferred item**：上面每一项都是必交。TSCAN-v0.1 把 Notebook 1 + 2 标了 deferred 直接发布；v0.2 回填了；v0.3 补了 Notebook 3。协议现在堵死了这三本都不能跳。

---

## 什么时候用这个 kit（什么时候别用）

适合用：

- ✅ 目标是一个 R / Bioconductor 包，输出明确（向量、矩阵、表、cluster ID、p-value）。
- ✅ 你能构造一个足够小的 canonical 输入 fixture（R reference 端到端 < 1 分钟）。
- ✅ 上游 R 包开源，license 你能匹配。
- ✅ 你准备好投入 1–5 个工作日给一次干净的 port（Class A 更少，Class C 带 acceleration 更多）。

不适合用：

- ❌ 你想要的"R 包"是闭源的，或只在论文里描述没有可跑代码 — 没可执行规范 = 没 parity oracle。
- ❌ 算法关键依赖 R-only C++ 扩展或 S4-heavy 的 Bioconductor 类 — 协议处理算法函数，不处理框架耦合的类。
- ❌ 你想要一个**比 R 更好**而不是相同的 Python 算法。这个 kit 拒绝放宽 gate；想优化算法，等 port 落地后 fork。
- ❌ 你目标是 GPU-only kernel 而没有 CPU reference — parity oracle 没东西比对。

---

## 进化-RL 类比（一段话）

Acceleration 循环是 **verifier-guided test-time search**，不是 weight-update RL — 而且**不是 metric optimization**：

| 组件 | 对应 |
|---|---|
| **Policy** | LLM in-context（不微调，不改权重）。 |
| **Action** | 一条来自 `ACCELERATION_PLAYBOOK.md` 的代数重写（Woodbury、X⊤X 缓存、稀疏行截断、MST ⊆ Delaunay…）。 |
| **Environment** | parity test + canonical fixture 上的 3-run-mean 钟表（见 [EVALUATION.md](EVALUATION.md)）。 |
| **Reward** | `r_t = φ(a_t) · speedup(a_t)` — gate 必须仍过（`φ = 1`），然后墙钟加速比给 admissible 候选排名。 |
| **Best-so-far register** | in-progress port 的最后一次 commit。后续重写破坏 parity 即回滚。 |

> **不做的事**：改进算法的生物学 metric。重构的目标是 R reference 的**相同**输出，不是"更好"的输出。每个 port 出两图：
>
> - `time vs iteration` — 重写被接受时单调下降。
> - `accuracy vs iteration` — 在天花板上平；每个凹点标注是哪个数学近似导致的。

模型权重不变。搜索发生在一个 coding-agent session 内，parity test 当 oracle，墙钟当 cost function。

---

## 最终产物 — reconstruction report

parity gate 通过 + Acceleration 循环结束后，agent 填 [`RECONSTRUCTION_REPORT.md`](templates/RECONSTRUCTION_REPORT.template.md)。8 节：

1. **Identity** — 包、上游版本、算法分类、阈值、最终 parity、audit 分类 A/B/C、LOC、vs R 加速比。
2. **R 函数覆盖率审计** — `NAMESPACE` 每个 export 函数在表里（ported / 带理由的 skipped）。`engine.r_function_audit` 自动填。另列**从 omicverse 复用的依赖**（生态审计 — 通过复用上游 py- 镜像节省了多少 LOC）。
3. **Parity 证据** — per-output 度量值、per-fixture 墙钟 + parity、可复现的 reference 命令。
4. **Acceleration 证据** — 嵌入双图、accepted vs rejected 重写 + admissibility 证明。
5. **代码质量审计** — `pip install` + `pytest` 绿 + 3 本必交 notebook 已执行 + license 兼容 + 版本固定。**全部必填。**
6. **已知限制** — 诚实列 port 不做的事；绝不当作放宽 gate 的借口。
7. **集成进 omicverse** — vendor 位置、public API 暴露、tutorial slot。
8. **签收** — 作者、日期、active 时间、最终 audit 分类。

这就是"这个 port 完成了"对外呈现的形式。

---

## 进化历史 — 协议怎么走到这里

协议靠真实 port 暴露的 anti-pattern 一版版打补丁来的。每个版本映射到一个真实 port 的失败模式；kit 靠 closing 这些 failure 增长，不靠推测。

| 版本 | 改了什么 | 为什么 |
|---|---|---|
| v1 | 初始 5 步协议 + parity 分类 + acceleration playbook | reference-driven 跨语言合成的基线。 |
| v2 | 增 [`EVALUATION.md`](EVALUATION.md)（双图评估、去热启动计时）+ [`ITERATION_LOG.md`](templates/ITERATION_LOG.template.md) + 结构化 [`RECONSTRUCTION_REPORT.md`](templates/RECONSTRUCTION_REPORT.template.md) | 用户澄清："重构是保证准确度，搜索是为速度" — 不是 metric optimization。 |
| v3 | 增 [`DISCOVERY.md`](DISCOVERY.md)（Phase 0.5）+ `engine/discover_omicverse_deps.py` | py-TSCAN 中途靠运气发现了 `py-mclustR`；协议现在强制在 Step 1 检查。 |
| v4 | 增 [`NOTEBOOKS.md`](NOTEBOOKS.md) — 两本必交 notebook（`compare_R_vs_Python`、`tutorial_<dataset>`） | py-TSCAN-v0.1 标了 deferred 直接发布；v0.2 回填。 |
| v5 | 增 Notebook 3（`function_by_function_R_parity`）— R⇄Python 参数字典 | 前两本没覆盖 R 用户逐行迁移自己的代码。 |
| v6（当前） | env var 改通用名（`PYTHON_TEST_ENV` / `R_TEST_ENV`）+ `REBUILDR_ORG` env var + [`SETUP.md`](SETUP.md) + [`engine/smoke_test.py`](engine/smoke_test.py) + `requirements.txt` + 一次 portable-paths 扫描 | Portability 审计发现第二个用户不能 clone-and-go — 得 grep kit 找硬编码路径。 |

---

## 本协议下已发布的 port

完整的 trajectory inference 列表见 [`examples/ROADMAP_TRAJ.md`](examples/ROADMAP_TRAJ.md)。

| 状态 | Port | 日期 | Audit | 加速比 | 备注 |
|---|---|---|---|---|---|
| ✅ | [py-monocle2](https://github.com/omicverse/py-monocle2) | 2026-04 | C | 102× | MST ⊆ Delaunay + Woodbury + X⊤X cache + 稀疏 R |
| ✅ | [py-mclustR](https://github.com/omicverse/py-mclustR) v0.2.0 | 2026-05 | A | — | 修了 TSCAN 暴露的 Fraley 1998 hcVVV bug |
| ✅ | [py-TSCAN](https://github.com/omicverse/py-TSCAN) | 2026-05 | A | ~28× | Class A + 3 notebook + 完整 discovery + 复用 py-mclustR |
| ⬜ 下一个 | py-tradeSeq | — | TBD | TBD | 引用密度最高（~152/yr）；Slingshot 的 DE-along-trajectory 搭档 |
| ⬜ | py-destiny | — | TBD | TBD | DPT 经典参考 |
| ⬜ | py-URD | — | TBD | TBD | 分支发育树 |
| ⬜ | py-SCORPIUS | — | TBD | TBD | dynbenchmark 线性轨迹冠军 |
| ⬜ | py-condiments | — | TBD | TBD | 多条件轨迹比较（Nat Commun 2024） |

---

## 常见问题（FAQ）

**Q：一次 port 大约要多久？**
A：Class A（纯翻译）：1–3 天。Class B（轻优化）：2–5 天。Class C（重算法重构 + acceleration）：1–2 周。py-TSCAN 是 Class A，约 6 小时；py-monocle2 是 Class C，约 2 周。

**Q：目标 R 包的依赖在 scipy / sklearn / pygam 里没有 Python 对应，怎么办？**
A：要么 (a) 先 port 那个依赖（顺手加进生态），要么 (b) 在 reconstruction report 里写"out of scope, 推迟到未来 minor release"。TSCAN port 对 `mclust` 走了 (a)（变成 `py-mclustR`），对 `ggplot2` 走了 (b)（plotting 推到 v0.2）。

**Q：能发到别的 GitHub org 吗？**
A：可以。跑 `engine.discover_omicverse_deps` 前导出 `REBUILDR_ORG=<your-org>`。Kit 不会自动把任何东西推到任何地方 — Phase 5 的 `gh repo create` 和 `twine upload` 都是显式的，你控制推到哪里。

**Q：Windows 能跑吗？**
A：在 Linux 上测过；macOS 应该可以。Windows 需要 WSL2 因为 kit 有一些 bash pipe 操作。

**Q：R Mclust / R rand / R 任何随机函数在我机器上结果不一样怎么办？**
A：这就是 manifest 固定 seed AND 分类 taxonomy 对随机输出降级到分布度量（KS / Wasserstein）的原因。如果你看到的平台级偏差超出 KS 容许范围，那是上游 R 包的 non-determinism bug，不是你 port 的问题 — 去那个 R 包 repo 报 issue。

**Q：我 port 的 `difftest` p-values 和 R 不一样，因为 `pygam` ≠ `mgcv`。怎么办？**
A：诚实回答（见 py-TSCAN Notebook 3）：GAM 实现在 small df 时拟合有实质差异。在 `MATH.md` 文档化，inference 类度量换成 Spearman-on-`-log10(p)` + top-K Jaccard，在 reconstruction report 的"已知限制"里点出来。**永远不要为了 p-values 元素级 "pass" 而放宽 gate。**

**Q：我的 Acceleration Agent 重写拿到 1.2× 加速但把 Pearson 从 1.0000 降到 0.9970，仍在阈值之上，接受吗？**
A：拒绝。Accuracy 允许下降**仅当** (B) bounded-ε 重写时、且扰动上界有闭式推导。没闭式上界的"小幅"经验下降是 bug，不是优化。

---

## License

Kit 本身 MIT。每个具体 port 匹配其上游 R 包的 license（上游 GPL ≥ 2 → GPL-3；上游 MIT/BSD/Apache → MIT；等等）。详见 `TEMPLATE.md §License decision matrix`。

---

## 起源

本协议提炼自把约 10 个经典生物信息学 R / Bioconductor 包重构为 Python 的工程经验（在 reference-driven parity gate 下）。底层方法论的 reference 是 "PolyPort" 菜谱（reference-driven cross-language library synthesis via LLM agents）。所有 case-study port 都在 `github.com/omicverse/py-*` 下；这个文件夹把菜谱抽出来，让每个后续 port 走同样的工程循环，不用从零推导。
