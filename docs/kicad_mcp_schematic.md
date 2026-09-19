# KiCad MCP 原理图生成

`/eda/schematic` 的首选原理图生成链路。eda_tools 服务作为 **MCP 客户端**，为每个生成任务
启动一个 [mcp-kicad-sch-api](https://github.com/circuit-synth/mcp-kicad-sch-api) MCP
server 子进程（stdio），通过标准 MCP 工具调用（`create_schematic` / `add_component` /
`add_label` / `save_schematic`）用真实 KiCad 库符号搭出 `.kicad_sch`，再用 kicad-cli 导出
SVG/ERC/网表。失败时自动回退到原有 SKiDL 链路。

## 流程（`eda_tools/mcp_schematic.py`）

1. CircuitIR 元件按 `type` 映射到 KiCad 库符号（映射表与 SKiDL generic builder 一致），
   按 subsystem 分列摆放（布局碰撞时自动加大间距重试，最多三轮）。
2. 保存一次，**本地解析 `.kicad_sch`** 计算每个引脚的精确坐标——不信任 server 的
   `get_component_pin_position`（其坐标变换有 bug；且 KiCad 库引脚 y 轴朝上，需翻转）。
3. **走线**：信号网络画真实导线——每个网络在元件列之间的走线槽里分配一条竖直干线，
   各成员引脚水平短线接入干线并打结点；几何冲突检测（共线重叠、T 型接头、导线穿越
   异己引脚）不过的网络回退为标签连接。电源网络（GND/+5V/+12V 等已知轨）保持
   `power:` 符号 + PWR_FLAG（行业标准画法，不拉线）。
4. 字母引脚符号（KiCad 10 的 `Q_NMOS` 引脚号是 G/S/D）按 IR `nodes` 顺序 + 网络成员
   语义（GND→源极、含 R*/U* 的网络→栅极）解析别名；推断不出时按"先漏后源"兜底。
5. **校验门**：kicad-cli 导出网表，与 IR 的网络划分做连通性等价比对（同符号同坐标引脚
   视为同一节点；符号上不存在的引脚（IR 幻觉引脚号）剔除并告警）；不一致直接抛错
   → 路由回退 SKiDL，绝不产出错误原理图。
6. 通过后导出 SVG（裁剪到内容）、ERC JSON，返回与 SKiDL 链路相同契约的结果
   （`generator: "mcp:mcp-kicad-sch-api"`）。

## 配置

- `CIRGPT_SCHEMATIC_BACKEND`：`mcp`（默认，MCP 优先 + SKiDL 兜底）｜ `skidl`（跳过 MCP）。
- KiCad 定位沿用 `KICAD_ROOT` / `KICAD_CLI`（见 START.bat）。

## 依赖与坑（换机必读）

- `eda_tools/requirements.txt` 钉了 `mcp>=1.0.0,<2`：vendored 的 MCP server wheel
  （`eda_tools/wheels/mcp_kicad_sch_api-0.2.2-py3-none-any.whl`，未发布 PyPI）用的是
  mcp 1.x 低层 `Server` API，mcp 2.x 已移除。**升级 mcp 到 2.x 会让 server 启动即崩**
  （`'Server' object has no attribute 'list_tools'`）。
- mcp 客户端 `ClientSession` 不要传 `read_timeout_seconds`——与该组合会话必崩
  （BrokenResourceError）；整体超时用外层 `asyncio.timeout`。
- 安装 mcp 可能连带升级 starlette/uvicorn，破坏 fastapi 0.109（`Router.__init__() got
  an unexpected keyword argument 'on_startup'`）。修复：`starlette==0.35.1`、
  `uvicorn[standard]==0.27.0`。
- MCP server 需 `KICAD_SYMBOL_DIR` 环境变量（本机 KiCad 在 D 盘，库缓存默认只扫 C 盘）。

## 已知限制

- 多单元符号（如 ATmega328P-P 实际为单单元但引脚有同坐标堆叠的 GND）通过"同坐标引脚
  合并"处理；IR 引脚号与真实芯片引脚语义不符时（DeepSeek 编的引脚号）按 IR 字面连接，
  ERC 会如实报未连接/未驱动的引脚。
- 布局为子系统分列的标签网格风格（与 SKiDL label-grid 同族），元件间无直连导线，
  属工程草稿质量；PCB 前需人工整理。
- 离线逻辑测试：`cd eda_tools && python -m tests.test_mcp_schematic_logic`。
