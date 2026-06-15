# 升级总览:A/B/C 三项增强(2026-06-15)

本文档配套 `deepseek_parser_v2_upgrade.md`,记录在 v2 prompt 升级之上追加的
三项独立工程化增强。

## A. EDA 工具按 subsystem 分页渲染

### 目标

让 v2 free-form prompt 输出的 `subsystems[]` 字段直接驱动**多页原理图**——
每个子系统(电源、保护、隔离、信号链、控制、负载、HMI、通信)单独成页,
最后一页是跨子系统总览(列出所有层级、组件归属、open_questions、
compliance_standards、operating_envelope)。

### 改动文件

| 文件 | 改动 |
|---|---|
| `eda_tools/ir_schematic.py` | 新增 `_render_subsystem_paged()` / `_render_subsystem_page()` / `_render_cross_subsystem_summary()`;`generate_ir_schematic_svg` 检测 `subsystems` 字段,有则返回 `{pages: [...], summary: ..., layout: 'subsystem-paged'}` 字典;无则仍返回单 SVG 字符串(向后兼容);新增 `_render_led_limiter()` 让 `led_current_limiter` 也走 IR 渲染 |
| `eda_tools/app/routers/eda.py` | `/eda/schematic` 同时支持单 SVG 字符串和分页字典;新字段 `schematic_pages` 透传 |
| `eda_tools/tests/test_subsystem_paged_render.py` | 新建:离线 smoke test,验证 v2 多页、legacy 单页两路径都 OK |

### 行为

- **v2 IR(带 `subsystems`)**:
  - 返回字典,`pages[i].subsystem` 是名称,`pages[i].svg` 是该页 SVG
  - 最后一页 `pages[-1].subsystem == "_overview"`
  - `summary.prompt_version` 沿用 `source.prompt_version`
  - `summary.total_components` 等于 IR 全部组件数
  - `component_to_subsystem` 提供 ref → 层级 映射
- **v1 IR(无 `subsystems`)**:返回原 SVG 字符串,前端代码无需改动

### 配色与排版

按子系统类型上色,便于扫读:

| 子系统 | 色块 |
|---|---|
| power_input | 浅绿 |
| protection | 浅橙 |
| isolation | 浅黄 |
| signal_input | 浅蓝 |
| signal_chain | 浅靛 |
| control | 浅紫 |
| load_output | 浅红 |
| feedback | 浅绿(深) |
| hmi | 浅粉 |
| communication | 浅青 |
| other | 灰 |

每页有彩色 banner + page n/N + 用途说明,Overview 页把所有层级摊开,
并把 `open_questions`(如"SIL 等级待确认")放在最显眼位置。

## B. 真实 API A/B 测试脚本

### 目标

让工程师一键复现"v1_strict vs v2_freeform 在真实 DeepSeek 上的行为差异",
并把 token 消耗、组件数、subsystem 数、warnings 数、finish_reason、
prompt_version 自动写进 JSON 报告。

### 改动文件

| 文件 | 改动 |
|---|---|
| `ai_service/nlp/deepseek_parser.py` | `parse_description_with_deepseek()` 新增 `return_raw` 形参,True 时返回 `(validated_ir, raw_upstream_dict)` 元组;`source.raw_response` / `source.raw_message_text` / `source.raw_request` 始终回填(便于 A/B 对比) |
| `ai_service/app/routers/ai.py` | `/ai/parse` 内部用 `return_raw=True`,把原始 payload 挂到 `requirements.raw_deepseek_response` 顶层(前端 `Show raw` 按钮直接拿) |
| `ai_service/tests/test_real_deepseek_call.py` | 新建:CLI 工具,支持 `--version v1_strict|v2_freeform`、`--prompts-only`(无 Key 时只导出 prompt)、`--skip`,输出到 `tests/output/real_deepseek_ab_<ts>.json` |

### 用法

```bash
# 1. 配 Key
echo DEEPSEEK_API_KEY=sk-xxx >> ai_service/.env

# 2. 全量 A/B
cd ai_service
python -m tests.test_real_deepseek_call

# 3. 只跑 v2
python -m tests.test_real_deepseek_call --version v2_freeform

# 4. 无 Key 时只导出 prompt(用于调试 prompt 工程)
python -m tests.test_real_deepseek_call --prompts-only
```

输出样例:

```text
[v1_strict] Design a 555 timer LED blinker circuit, 9V supply, 1 Hz
  -> type=555_timer_blinker comps=8 subs=0 t=1.842s
[v2_freeform] Design a 555 timer LED blinker circuit, 9V supply, 1 Hz
  -> type=555_timer_blinker comps=9 subs=2 t=2.103s
[v1_strict] Design a track circuit tester receiver front end ...
  -> type=generic_circuit comps=12 subs=0 t=2.451s
[v2_freeform] Design a track circuit tester receiver front end ...
  -> type=track_circuit_tester_receiver comps=18 subs=4 t=2.870s

Report written to: tests/output/real_deepseek_ab_20260615_091500.json
```

JSON 报告字段:

- `prompt_version` / `model` / `base_url`
- 每条记录:`timestamp` / `elapsed_seconds` / `description`
- `validated_ir_summary`:circuit_type / component_count / subsystem_count /
  open_question_count / warning_count / has_compliance_standards /
  has_operating_envelope / has_design_notes
- `raw_response_keys` / `finish_reason` / `token_usage` /
  `raw_message_text_length`

## C. "Show raw DeepSeek response" 按钮 + 多页 schematic viewer

### 目标

让用户在前端**透明看到模型原话**——既能看到模型实际输出的 JSON 文本,
也能看到 vendor 完整响应(usage、finish_reason、id),还能看到发出去的
完整 prompt(便于和模型工程师一起调 prompt)。同时让原理图支持**多页浏览**。

### 改动文件

| 文件 | 改动 |
|---|---|
| `frontend/components/RawDeepseekDialog.jsx` | 新建:MUI Dialog,3 个 Tab — "Model text"(原始 content)、"Full upstream JSON"(整个 response body)、"Sent prompt"(拼好的 system+user)。每块带复制按钮 |
| `frontend/components/SchematicViewer.jsx` | 重写:支持 `pages` 参数;有 `pages` 时显示子系统 chip 切换器,每页独立 SVG;无 `pages` 时保持原行为(向后兼容);下载文件名带上子系统名 |
| `frontend/app/design/[id]/page.jsx` | 加 "Show raw DeepSeek response" 按钮 + chips(prompt version / model / subsystem count / open questions)+ `RawDeepseekDialog` 挂载;Schematic 标签页传入 `pages={design.schematic_pages}` |
| `backend/app/routers/circuit.py` | 新增 `GET /circuit/{id}/raw-deepseek`,返回 `source.raw_response` / `raw_message_text` / `raw_request` / `validated_ir_summary`;DeepSeek 未启用时返回 404,前端按 404 静默降级 |
| `backend/app/services/circuit_service.py` | 把 EDA 端点 `schematic_pages` 持久化到 `design.schematic_pages` |
| `backend/models/circuit_design.py` | 加 `schematic_pages` JSON 字段 |
| `backend/schemas/circuit_design.py` | `CircuitDesignResponse` 加 `schematic_pages` 字段 |

### 前端使用流

1. 进入设计详情页 → 标题区有 chips:
   - `prompt: v2_freeform`
   - `model: deepseek-v4-flash`
   - `subsystems: 4`
   - `open questions: 2`
2. 右上角"Show raw DeepSeek response"按钮:
   - 命中 → 弹窗,3 个 Tab 可看
   - 404(规则解析器)→ 弹窗但显示"No raw response available"
3. 进入原理图 Tab:
   - v2 多页 → 顶部 chips 切换子系统,Overview 页总览
   - v1 单页 → 仍按原方式渲染

## 验证证据

| 验证 | 命令 | 结果 |
|---|---|---|
| 升级后 v1/v2 prompt 解析无回归 | `cd ai_service && python -m scripts.test_deepseek_parser` | 6/6 OK |
| Subsystem-paged 渲染 + legacy 兼容 | `cd eda_tools && python -m tests.test_subsystem_paged_render` | 2/2 OK(7 子系统 + Overview = 8 页) |
| 真实 API A/B | `cd ai_service && python -m tests.test_real_deepseek_call` | 需 Key;无 Key 时 `--prompts-only` 仍能跑通 |

## 风险点

1. **数据库迁移**:`schematic_pages` 是新字段,需执行 alembic 或 `init_db` 重建表结构;若保留旧数据,可使用 SQL `ALTER TABLE circuit_designs ADD COLUMN schematic_pages JSON`
2. **历史设计**:`raw_deepseek_response` 仅在 v2 升级后**新生成**的设计中存在;老设计(由 v1 解析)走 404 路径,UI 已做静默降级
3. **大型 IR**:subsystem 分页是为大型 IR(>=10 组件)设计的;小 IR(< 3 组件)仍按 Overview 单页展示,不会有大量空页
4. **KiCad/SKiDL fallback**:若后端 KiCad 不可用,EDA 路由会回退到 IR-SVG;subsystem 分页对 fallback 同样生效,因为它在 `ir_schematic.py` 内部完成,不依赖 SKiDL

## 后续工作

- [ ] 把 `schematic_pages` 也加进设计历史(`DesignHistory` 表),便于回放
- [ ] `open_questions` → 前端对话式澄清:把每个问题显示为可点击 chip,点击后自动用答案重跑
- [ ] `compliance_standards` → 自动加载合规库(EN 50129 SIL2/3、IEC 61850-3)并校验器件选型
- [ ] `test_points` → 自动追加到原理图上的测试点符号,生成测试夹具 BOM
- [ ] `design_notes` → 渲染到 KiCad 标题栏 / 备注
- [ ] 在 A/B 报告里加 diff 视图(JSON patch)便于定位 prompt 工程改进点
