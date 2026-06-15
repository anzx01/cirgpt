# DeepSeek Parser 升级指南(v1 → v2)

> 状态:**已实施** | 日期:2026-06-15 | 作者:cirgpt

## 1. 升级动机

旧版(`v1_strict`)system prompt 强制把 `circuit_type` 限制在 6 个固定模板
(led_current_limiter / capacitor_discharge_led / rc_low_pass_filter /
555_timer_blinker / opamp_inverting / opamp_non_inverting),其它请求一律
降级为 `generic_circuit`。这把 DeepSeek 强大的领域知识浪费在"猜模板"上,
让"轨道电路综合测试仪"、"BLDC 驱动器"、"电池 BMS"、"LoRa 节点"这类
真实工程需求被迫塞进不匹配的模板,产生大量误判和回退。

新版(`v2_freeform`)**取消模板白名单**,允许 DeepSeek 自创 snake_case
标识符描述电路,并要求输出 10 层子系统结构 + 丰富的元数据
(domain / compliance_standards / subsystems / test_points /
operating_envelope / interfaces / design_notes / open_questions),
更接近真实硬件设计流程。

## 2. 行为对比

| 维度 | v1_strict(旧) | v2_freeform(新,默认) |
|---|---|---|
| `circuit_type` 取值 | 仅 6 个白名单 | 自由 snake_case,自动归一化 |
| 复杂请求(如轨道电路) | 强降级为 `generic_circuit` | 自创 `track_circuit_tester_receiver` |
| 子系统/分层信息 | 无 | 10 层引导(power/protection/...) |
| 组件级元数据(封装/厂家/料号) | 无 | 透传 tolerance / package / mfr / mfr_pn |
| 设计备注/疑问 | 无 | `design_notes` + `open_questions` |
| 合规标准引用 | 无 | `compliance_standards` 字段 |
| 6 个旧模板的角色硬校验 | 强制 | **保留**(向后兼容) |
| `unsupported` 触发条件 | 任何非白名单 | 真正非电路请求(空/乱码) |
| 旧 SPICE 兼容(`generate_from_ir`) | 正常 | 正常(走 `generic_circuit` 分支) |
| `max_tokens` | 2500 | 4000(承载更丰富元数据) |

## 3. 配置切换

`ai_service/.env` 新增:

```bash
# 取值 v1_strict 或 v2_freeform,默认 v2_freeform
DEEPSEEK_PROMPT_VERSION=v2_freeform
```

无需重启进程外的其它配置。所有 v1 行为(角色硬校验、白名单)已作为
"向后兼容子集"在 v2 中保留。

## 4. 代码改动清单

| 文件 | 改动 |
|---|---|
| `ai_service/nlp/prompts/__init__.py` | 新建:prompt 注册表命名空间 |
| `ai_service/nlp/prompts/v1_strict.py` | 新建:旧版 prompt 原样迁出 |
| `ai_service/nlp/prompts/v2_freeform.py` | 新建:新版自由形式 prompt |
| `ai_service/nlp/prompts/registry.py` | 新建:`get_active_system_prompt()` |
| `ai_service/nlp/deepseek_parser.py` | 重写:① prompt 来源切换 ② 校验软化 ③ 字段透传 ④ prompt 版本戳 |
| `ai_service/.env.example` | 新增 `DEEPSEEK_PROMPT_VERSION` |
| `ai_service/scripts/test_deepseek_parser.py` | 新建:离线 smoke test |
| `docs/deepseek_parser_v2_upgrade.md` | 本文档 |

## 5. 新版输出示例(给"轨道电路综合测试仪接收机前端"的请求)

```json
{
  "schema_version": "1.0",
  "supported": true,
  "circuit_type": "track_circuit_tester_receiver",
  "title": "Track circuit tester receiver front end",
  "description": "...",
  "domain": "railway",
  "compliance_standards": ["EN 50129", "TB/T 3202"],
  "components": [
    {
      "ref": "R1",
      "type": "resistor",
      "value": 2000000,
      "unit": "ohm",
      "tolerance_pct": 0.1,
      "voltage_rating_v": 250,
      "package": "2512",
      "nodes": ["TR_A", "A1"],
      "role": "voltage_divider",
      "subsystem": "signal_input"
    },
    {"ref": "U1", "type": "opamp", "value": "ADA4528", "nodes": ["A1","A2","DIFF_OUT","VCC_A","VEE_A"], "role": "amplifier", "subsystem": "signal_chain"},
    {"ref": "U2", "type": "isolated_amplifier", "value": "ISO224", "nodes": ["DIFF_OUT","ISO_OUT","VDD1","VDD2","0"], "role": "isolation", "subsystem": "isolation"},
    {"ref": "U3", "type": "adc", "value": "ADS8860", "nodes": ["ISO_OUT","ADC_OUT","VREF","VDD"], "role": "adc", "subsystem": "signal_chain"}
  ],
  "subsystems": [
    {"name": "power_input",  "purpose": "DC supply",          "component_refs": ["V1"]},
    {"name": "signal_input", "purpose": "Differential HV divider", "component_refs": ["J1","R1","R2"]},
    {"name": "isolation",    "purpose": "5 kV barrier",        "component_refs": ["U2"]},
    {"name": "signal_chain", "purpose": "Buffer + ADC",        "component_refs": ["U1","U3"]}
  ],
  "operating_envelope": {"temp_min_c": -25, "temp_max_c": 70, "ip_rating": "IP54"},
  "design_notes": ["Divider chosen for 100:1 attenuation..."],
  "open_questions": ["Confirm maximum sustained field voltage", "Confirm SIL class"],
  "warnings": [
    "circuit_type 'track_circuit_tester_receiver' is free-form; downstream EDA generators will fall back to the generic_circuit pipeline."
  ],
  "source": {
    "mode": "deepseek",
    "model": "deepseek-v4-flash",
    "prompt_version": "v2_freeform",
    "rationale": ["R1:R2 = 100:1 to bring 110V to 1.1V"]
  }
}
```

## 6. 离线验证

无需 DeepSeek Key,跑:

```bash
cd ai_service
python -m scripts.test_deepseek_parser
```

期望输出:

```
Active prompt version: v2_freeform
Registered prompts: ['v1_strict', 'v2_freeform']
OK   v1 555 with all roles (expect supported=True)
OK   v1 555 missing timing_rb (expect ValueError): raised ValueError
OK   v2 555 with all roles (expect supported=True)
OK   v2 free-form track circuit tester (expect supported=True)
OK   v2 bad circuit_type (expect normalized)
OK   v2 empty components (expect supported=False)
All smoke checks passed.
```

## 7. 回退方案

如果新版在生产中表现不佳:

1. **立刻回退**:在 `ai_service/.env` 改 `DEEPSEEK_PROMPT_VERSION=v1_strict`,重启 ai_service
2. **对比分析**:同一请求的 v1 vs v2 输出都可通过 `source.prompt_version` 字段区分
3. **A/B 测试**:保留两个 prompt,前端加 `?prompt_version=v1_strict` 查询参数切换

## 8. 后续工作(可选)

- [ ] 让 EDA 服务(`eda_tools`)识别 `subsystem` 字段,原理图按子系统分页/分块
- [ ] `compliance_standards` → 自动校验器件选型(EN 50129 SIL2/3 库)
- [ ] `manufacturer_part` → 自动从 BOM 库查库存/价格
- [ ] `open_questions` → 前端提示用户澄清,触发二次解析
- [ ] 增加 `test_points` → 自动生成测试夹具 BOM
- [ ] 把 `design_notes` 渲染到 KiCad 原理图标题栏/备注区
