# 第三方声明 (Third-Party Notices)

本仓库使用 ISC 许可证发布，并依赖以下第三方开源软件包和外部 EDA 工具，各自保留其原有许可证。

## 重要许可证说明

### GPL 兼容性说明

本项目 **不再依赖** PySpice pip 包（GPLv3）。电路仿真功能通过直接调用
系统安装的 `ngspice` 可执行文件实现（ngspice 采用 BSD/ISC 兼容许可证）。

如果用户自行在本项目中重新引入 PySpice 依赖，需注意其 GPLv3 许可证
与本项目的 ISC 许可证不兼容，可能产生版权合规义务。

### Apache 2.0 专利条款说明

`transformers` 和 `huggingface-hub` 采用 Apache 2.0 许可证，该许可证包含
明确的专利授权与终止条款。在涉及专利的商业场景中使用时，建议咨询法律顾问。

---

## 直接依赖项许可证清单

### 后端服务 (`backend/requirements.txt`)

| 库 | 许可证 |
|---|---|
| fastapi | MIT |
| uvicorn | BSD 3-Clause |
| sqlalchemy | MIT |
| pydantic | MIT |
| python-jose | MIT |
| passlib | BSD 3-Clause |
| httpx | BSD 3-Clause |
| redis | MIT |
| celery | BSD 3-Clause |
| python-socketio | MIT |
| aiohttp | Apache 2.0 |
| python-dotenv | BSD 3-Clause |

### AI 服务 (`ai_service/requirements.txt`)

| 库 | 许可证 | 备注 |
|---|---|---|
| torch | BSD | |
| transformers | Apache 2.0 | 含专利条款 |
| huggingface-hub | Apache 2.0 | 含专利条款 |
| spacy | MIT | |
| numpy | BSD | |
| pandas | BSD 3-Clause | |
| httpx | BSD 3-Clause | |
| pydantic | MIT | |

### EDA 工具服务 (`eda_tools/requirements.txt`)

| 库 | 许可证 | 备注 |
|---|---|---|
| skidl | MIT | |
| numpy | BSD | |
| scipy | BSD 3-Clause | |
| matplotlib | PSF (BSD 兼容) | |
| Pillow | HPND | |
| pandas | BSD 3-Clause | |
| openpyxl | MIT | |
| python-dotenv | BSD 3-Clause | |
| pydantic | MIT | |
| httpx | BSD 3-Clause | |
| svgwrite | MIT | |

### 前端 (`frontend/package.json`)

| 库 | 许可证 |
|---|---|
| next | MIT |
| react / react-dom | MIT |
| @mui/material | MIT |
| @mui/icons-material | MIT |
| @emotion/react | MIT |
| @emotion/styled | MIT |
| socket.io-client | MIT |
| @svgdotjs/svg.js | MIT |
| axios | MIT |
| recharts | MIT |

---

## 外部工具

本项目与以下外部工具集成，这些工具不属于本项目，亦不从本仓库重新分发。
请从各工具官方来源安装，并单独审查其许可证：

| 工具 | 许可证 | 官方来源 |
|---|---|---|
| ngspice | BSD 3-Clause | https://ngspice.sourceforge.io |
| KiCad | GPLv3 (仅系统工具，不作为库链接) | https://www.kicad.org |
| SKiDL | MIT | https://github.com/devbisme/skidl |

> **KiCad 说明**：KiCad 以 GPLv3 发布，但本项目通过系统调用（subprocess）与其交互，
> 而非作为链接库导入，因此不产生 GPL 传染义务。

---

## SPICE 模型与厂商文件

供应商提供的 SPICE 模型、仿真器捆绑包、下载的模型权重、本地虚拟环境
以及运行时生成的文件，不得提交到本仓库，除非已审查并记录其再分发权利。

本地 `Spice64/` 目录已被 `.gitignore` 排除并从 Git 追踪中移除，
因为它包含第三方 ngspice 示例和具有独立版权条款的厂商模型文件。

---

## 生成完整许可证报告

```bash
# Python 依赖
pip install pip-licenses
pip-licenses --format=markdown --with-urls

# Node.js 依赖
npx license-report --output=table
```
