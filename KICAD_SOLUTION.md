# 🎯 方案：通过AI + KiCad API 生成完美原理图

**目标**: 使用AI理解需求，通过KiCad Python API生成专业级原理图  
**可行性**: ✅ **完全可行**  
**预计时间**: 2-4周开发

---

## 🔍 技术调研

### KiCad Python API

**KiCad 6.0+** 提供了完整的Python API：

```python
import pcbnew
from pcbnew import *

# KiCad Python API 支持：
# 1. 原理图编辑 (Eeschema)
# 2. PCB编辑 (Pcbnew)
# 3. 元件库访问
# 4. 符号库访问
# 5. 自动化脚本
```

**官方文档**: https://docs.kicad.org/doxygen-python/

---

## 🏗️ 架构设计

### 新架构

```
用户需求 (自然语言)
    ↓
AI服务 (解析需求 → CircuitIR)
    ↓
KiCad生成服务 (新增) ← **核心模块**
    ├─ 元件符号库
    ├─ 自动布局算法
    ├─ KiCad Python API
    └─ 原理图生成
    ↓
KiCad文件 (.kicad_sch, .kicad_pcb)
    ↓
SVG导出 / 在线查看
```

---

## 📦 需要的组件

### 1. KiCad生成服务

**位置**: `kicad_service/` (新建)

**功能**:
- 接收CircuitIR
- 调用KiCad API生成原理图
- 自动布局元件
- 导出SVG预览

### 2. 元件符号映射库

**位置**: `kicad_service/symbol_mapper.py`

**功能**:
```python
# 将通用元件名映射到KiCad符号库
{
    "UA741": "Amplifier_Operational:UA741",
    "NE555": "Timer:NE555",
    "LED": "Device:LED",
    "resistor": "Device:R",
    "capacitor": "Device:C"
}
```

### 3. 自动布局引擎

**位置**: `kicad_service/layout_engine.py`

**功能**:
- 分析电路拓扑
- 计算最佳元件位置
- 自动连线（正交布线）

---

## 🔧 技术实现方案

### 方案1: KiCad Python API (推荐) ⭐⭐⭐⭐⭐

**技术栈**:
```python
import pcbnew
from pcbnew import EDA_TEXT_HJUSTIFY_T, EDA_TEXT_VJUSTIFY_T
from pcbnew import VECTOR2I

# KiCad 7/8 Python API
```

**示例代码**:
```python
# 1. 创建原理图
board = pcbnew.LoadBoard("my_circuit.kicad_pcb")

# 2. 添加元件
module = pcbnew.FootprintLoad("Device", "R_0805")
module.SetPosition(VECTOR2I(50000000, 50000000))
board.Add(module)

# 3. 添加连线
track = pcbnew.PCB_TRACK(board)
track.SetStart(VECTOR2I(x1, y1))
track.SetEnd(VECTOR2I(x2, y2))
board.Add(track)

# 4. 保存
pcbnew.SaveBoard("output.kicad_pcb", board)
```

**优点**:
- ✅ 官方API，稳定可靠
- ✅ 支持所有KiCad功能
- ✅ 生成标准KiCad文件
- ✅ 可以用KiCad打开编辑

**缺点**:
- ⚠️ 需要安装KiCad
- ⚠️ 学习曲线（API文档）

### 方案2: SKiDL (Python库) ⭐⭐⭐⭐

**已经在项目中**: `eda_tools/schematic_gen/schematic_generator.py`

**技术栈**:
```python
from skidl import *

# 定义电路
vin = V(ref='Vin', value='SIN(0 0.1 1k)')
r1 = R(value='10k', ref='R1')
r2 = R(value='100k', ref='R2')
opamp = Part('Amplifier_Operational', 'UA741', ref='U1')

# 连接
r1[1, 2] += vin['p'], opamp['IN-']
r2[1, 2] += opamp['OUT'], opamp['IN-']

# 生成网表
generate_netlist()

# 生成原理图
generate_schematic()  # 输出KiCad格式
```

**优点**:
- ✅ 纯Python，易于集成
- ✅ 支持KiCad符号库
- ✅ 代码即电路
- ✅ 已经部分集成

**缺点**:
- ⚠️ 自动布局质量一般
- ⚠️ 需要手动优化布局

### 方案3: 混合方案（推荐实施）⭐⭐⭐⭐⭐

**架构**:
```
AI服务 (解析需求)
    ↓
CircuitIR (标准格式)
    ↓
SKiDL (生成网表和初始布局)
    ↓
KiCad API (优化布局、美化)
    ↓
完美的KiCad原理图
```

**优点**:
- ✅ 利用SKiDL快速生成
- ✅ 利用KiCad API精细控制
- ✅ 两者优势互补

---

## 📋 实施计划

### Phase 1: 基础框架 (第1周)

**任务**:
1. ✅ 创建 `kicad_service/` 目录
2. ✅ 安装 KiCad 8 + Python API
3. ✅ 测试 KiCad Python API 基础功能
4. ✅ 设置SKiDL环境

**交付物**:
- 可以用Python创建空白KiCad原理图
- 可以添加基本元件（电阻、电容）

### Phase 2: 元件符号库 (第2周)

**任务**:
1. ✅ 建立元件映射表
2. ✅ 实现符号查找功能
3. ✅ 支持常用IC（555, 741, LM358等）
4. ✅ 测试符号放置

**交付物**:
- 元件符号映射库
- 可以放置各种IC到原理图

### Phase 3: 自动布局 (第3周)

**任务**:
1. ✅ 分析电路拓扑
2. ✅ 实现力导向布局算法
3. ✅ 实现正交布线算法
4. ✅ 优化布局美观度

**交付物**:
- 自动布局引擎
- 自动连线功能

### Phase 4: 集成和优化 (第4周)

**任务**:
1. ✅ 集成到后端服务
2. ✅ 添加SVG导出
3. ✅ 测试完整流程
4. ✅ 性能优化

**交付物**:
- 完整的KiCad生成服务
- 前端可以显示专业原理图

---

## 🔨 技术细节

### 1. CircuitIR → SKiDL 转换

**代码位置**: `kicad_service/circuit_to_skidl.py`

```python
def circuit_ir_to_skidl(circuit_ir: Dict) -> Circuit:
    """
    Convert CircuitIR to SKiDL circuit
    
    Args:
        circuit_ir: CircuitIR dict
        
    Returns:
        SKiDL Circuit object
    """
    from skidl import Circuit, Part, Net
    
    circuit = Circuit()
    
    # 创建所有元件
    components = {}
    for comp in circuit_ir['components']:
        if comp['type'] == 'resistor':
            components[comp['ref']] = Part('Device', 'R', 
                value=f"{comp['value']}{comp['unit']}", 
                ref=comp['ref'])
                
        elif comp['type'] == 'ideal_opamp':
            components[comp['ref']] = Part('Amplifier_Operational', 'UA741',
                ref=comp['ref'])
    
    # 连接网络
    nets = {}
    for net in circuit_ir['nets']:
        net_obj = Net(net['name'])
        nets[net['name']] = net_obj
        
        # 连接所有引脚到这个网络
        for conn in net['connections']:
            ref, pin = conn.split('.')
            components[ref][int(pin)] += net_obj
    
    return circuit
```

### 2. SKiDL → KiCad 原理图

```python
def generate_kicad_schematic(circuit_ir: Dict) -> str:
    """
    Generate KiCad schematic file
    
    Returns:
        Path to .kicad_sch file
    """
    from skidl.tools.kicad8 import generate_schematic
    
    # 转换为SKiDL
    circuit = circuit_ir_to_skidl(circuit_ir)
    
    # 生成KiCad原理图
    output_path = f"/tmp/circuit_{uuid.uuid4()}.kicad_sch"
    generate_schematic(circuit, output_path)
    
    # 优化布局（使用KiCad API）
    optimize_layout(output_path)
    
    return output_path
```

### 3. 自动布局优化

```python
def optimize_layout(schematic_path: str):
    """
    Optimize component placement using force-directed algorithm
    """
    import pcbnew
    
    # 加载原理图
    sch = load_schematic(schematic_path)
    
    # 获取所有元件
    components = sch.GetComponents()
    
    # 力导向布局
    positions = force_directed_layout(components)
    
    # 应用位置
    for comp, pos in zip(components, positions):
        comp.SetPosition(VECTOR2I(pos.x, pos.y))
    
    # 自动布线
    auto_route(sch)
    
    # 保存
    sch.Save()
```

### 4. 导出SVG预览

```python
def export_svg(kicad_sch_path: str) -> str:
    """
    Export KiCad schematic to SVG
    """
    import subprocess
    
    svg_path = kicad_sch_path.replace('.kicad_sch', '.svg')
    
    # 使用KiCad CLI导出
    subprocess.run([
        'kicad-cli', 'sch', 'export', 'svg',
        '--output', svg_path,
        kicad_sch_path
    ])
    
    return svg_path
```

---

## 🚀 快速原型

### 第一个完整示例（运放电路）

```python
# kicad_service/examples/opamp_example.py

from skidl import *

# 创建电路
vin = V(ref='Vin', dc_value='0V', ac_value='1V')
vcc = V(ref='VCC', dc_value='15V')
vee = V(ref='VEE', dc_value='-15V')

r1 = R(value='10k', ref='R1')
r2 = R(value='100k', ref='R2')
opamp = Part('Amplifier_Operational', 'UA741', ref='U1')

# 连接
gnd = Net('GND')
vin_net = Net('IN')
sum_net = Net('SUMMING')
out_net = Net('OUTPUT')

vin['p'] += vin_net
vin['n'] += gnd

r1[1] += vin_net
r1[2] += sum_net

r2[1] += out_net
r2[2] += sum_net

opamp['+'] += gnd  # 同相端接地
opamp['-'] += sum_net  # 反相端
opamp['OUT'] += out_net
opamp['V+'] += vcc['p']
opamp['V-'] += vee['p']

# 生成原理图
generate_schematic(file_='opamp_inverting.kicad_sch')

print("✅ KiCad原理图已生成: opamp_inverting.kicad_sch")
```

---

## 📊 预期效果

### 生成的原理图将包含

- ✅ **专业的IC符号**: UA741三角形运放符号
- ✅ **正确的引脚标注**: +/-/OUT/V+/V-
- ✅ **清晰的网络连接**: 正交布线
- ✅ **元件标注**: R1 10k, R2 100k, U1 UA741
- ✅ **电源符号**: VCC/VEE/GND
- ✅ **可编辑**: 可以在KiCad中打开编辑

### 质量对比

| 特性 | 当前系统 | 新方案 |
|------|----------|--------|
| IC符号 | ❌ 矩形框 | ✅ 专业符号 |
| 引脚标注 | ⚠️ 数字 | ✅ 功能名称 |
| 布线 | ⚠️ 直线 | ✅ 正交布线 |
| 可编辑 | ❌ | ✅ KiCad原生 |
| 美观度 | ⭐⭐ | ⭐⭐⭐⭐⭐ |

---

## 💰 成本评估

### 开发成本

- **时间**: 2-4周（1人全职）
- **工具**: 免费（KiCad开源，SKiDL开源）
- **风险**: 低（成熟的技术栈）

### 运行成本

- **KiCad**: 开源免费
- **服务器**: 现有服务器即可
- **存储**: .kicad_sch 文件很小（几KB）

---

## 🎯 立即开始

### 第一步：验证技术可行性

```bash
# 1. 安装KiCad 8
# Download from: https://www.kicad.org/download/

# 2. 安装SKiDL
pip install skidl

# 3. 测试
cd kicad_service
python examples/opamp_example.py

# 4. 在KiCad中打开
kicad opamp_inverting.kicad_sch
```

### 第二步：创建KiCad服务

```bash
# 创建服务目录
mkdir -p kicad_service/app/{routers,services,utils}

# 创建文件
touch kicad_service/app/main.py
touch kicad_service/app/services/schematic_generator.py
touch kicad_service/app/services/symbol_mapper.py
touch kicad_service/app/services/layout_engine.py
```

### 第三步：实现基础功能

创建 `kicad_service/app/main.py`:
```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any

app = FastAPI(title="KiCad Schematic Generator", version="1.0.0")

class SchematicRequest(BaseModel):
    circuit_ir: Dict[str, Any]

@app.post("/generate")
async def generate_schematic(request: SchematicRequest):
    """
    Generate KiCad schematic from CircuitIR
    """
    try:
        from services.schematic_generator import generate_kicad_schematic
        
        # 生成KiCad原理图
        sch_path = generate_kicad_schematic(request.circuit_ir)
        
        # 导出SVG
        svg_path = export_svg(sch_path)
        
        # 读取SVG
        with open(svg_path, 'r') as f:
            svg_content = f.read()
        
        return {
            "success": True,
            "svg": svg_content,
            "kicad_file": sch_path,
            "message": "Professional schematic generated with KiCad"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    return {"message": "KiCad Schematic Generator Service", "version": "1.0.0"}
```

---

## 📚 资源链接

### 官方文档
- KiCad Python API: https://docs.kicad.org/doxygen-python/
- SKiDL: https://github.com/devbisme/skidl
- KiCad文件格式: https://dev-docs.kicad.org/en/file-formats/

### 示例代码
- SKiDL Examples: https://github.com/devbisme/skidl/tree/master/examples
- KiCad Scripts: https://github.com/KiCad/kicad-python

### 元件库
- KiCad官方库: https://gitlab.com/kicad/libraries/kicad-symbols
- SnapEDA: https://www.snapeda.com/ (第三方符号)

---

## ✅ 下一步行动

### 你需要决定

1. **是否立即开始实施？**
   - 如果是 → 我可以帮你：
     - 搭建KiCad服务框架
     - 实现第一个示例（运放电路）
     - 编写测试代码

2. **是否需要我先做POC？**
   - 创建一个完整的运放电路示例
   - 验证KiCad API所有功能
   - 测试SKiDL生成质量

3. **优先级排序**
   - 哪种电路类型最重要？（运放/555/LED/滤波器）
   - 先实现哪些功能？（符号/布局/布线）

---

**这个方案完全可行！** 

KiCad是开源的，有完整的Python API，加上SKiDL的帮助，我们可以生成专业级的原理图。

**你想现在就开始吗？**

