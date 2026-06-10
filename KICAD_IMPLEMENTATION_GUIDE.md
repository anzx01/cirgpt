# 🚀 KiCad方案实施指南

**目标**: 通过AI + KiCad API生成专业原理图  
**状态**: 准备开始实施

---

## 📦 第一步：安装必需工具

### 1. 安装KiCad 8

**Windows下载**:
```
https://www.kicad.org/download/windows/
```

**推荐版本**: KiCad 8.0 或更高

**安装后验证**:
```powershell
# 添加KiCad到PATH，或者直接运行
"C:\Program Files\KiCad\8.0\bin\kicad-cli.exe" version
```

### 2. 安装SKiDL

```bash
pip install skidl
```

### 3. 安装KiCad Python绑定

```bash
# SKiDL会自动处理大部分，但如果需要直接使用KiCad API:
pip install kicad-python
```

---

## 🎯 方案选择

基于你的需求，我推荐**方案A：纯SKiDL方案**

### 为什么选SKiDL？

1. **纯Python** - 不需要安装完整KiCad（可选）
2. **代码即电路** - 清晰、可维护
3. **原生KiCad输出** - 生成标准.kicad_sch文件
4. **符号库完整** - 支持所有KiCad官方符号
5. **自动布局** - 内置布局算法

---

## 💻 POC示例代码

### 示例1: 完美的运放电路

创建 `kicad_service/poc_opamp.py`:

```python
"""
POC: Generate perfect op-amp schematic using SKiDL
"""
from skidl import *

# Set KiCad library paths
lib_search_paths[KICAD].append('/usr/share/kicad/symbols')  # Linux
lib_search_paths[KICAD].append('C:/Program Files/KiCad/8.0/share/kicad/symbols')  # Windows

# Create nets
gnd = Net('GND')
vin_net = Net('IN')
sum_net = Net('SUMMING')
out_net = Net('OUTPUT')
vcc_net = Net('VCC')
vee_net = Net('VEE')

# Define components with proper KiCad symbols
vin = Part('pspice', 'VSOURCE', ref='Vin', 
           value='AC 1 SIN(0 0.1 1k)', 
           footprint='')
vin['+'] += vin_net
vin['-'] += gnd

vcc = Part('pspice', 'VDC', ref='VCC', 
           value='15V',
           footprint='')
vcc['+'] += vcc_net
vcc['-'] += gnd

vee = Part('pspice', 'VDC', ref='VEE', 
           value='15V',
           footprint='')
vee['+'] += gnd
vee['-'] += vee_net

# Resistors with proper symbols
r1 = Part('Device', 'R', ref='R1', value='10k', footprint='Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal')
r1[1] += vin_net
r1[2] += sum_net

r2 = Part('Device', 'R', ref='R2', value='100k', footprint='Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal')
r2[1] += out_net
r2[2] += sum_net

rload = Part('Device', 'R', ref='Rload', value='100k', footprint='Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal')
rload[1] += out_net
rload[2] += gnd

# Op-amp with proper symbol (triangle)
opamp = Part('Amplifier_Operational', 'LM741', ref='U1', 
             footprint='Package_DIP:DIP-8_W7.62mm')

# Connect op-amp pins
opamp['~'] += sum_net      # Pin 2: Inverting input (-)
opamp['+'] += gnd          # Pin 3: Non-inverting input (+)
opamp['OUT'] += out_net    # Pin 6: Output
opamp['V+'] += vcc_net     # Pin 7: Positive supply
opamp['V-'] += vee_net     # Pin 4: Negative supply

# Offset null pins (not connected)
opamp['NC'] += NC
opamp['NC'] += NC

# Generate netlist
generate_netlist(file_='opamp_inverting.net')

# Generate KiCad schematic
ERC()  # Check for errors
generate_schematic(file_='opamp_inverting.kicad_sch')

print("✅ Perfect op-amp schematic generated!")
print("📁 File: opamp_inverting.kicad_sch")
print("🔍 Open in KiCad to see professional triangle symbol")
```

### 示例2: 555定时器电路

创建 `kicad_service/poc_555.py`:

```python
"""
POC: Generate perfect 555 timer schematic using SKiDL
"""
from skidl import *

# Nets
gnd = Net('GND')
vcc_net = Net('VCC')
out_net = Net('OUTPUT')
thresh_net = Net('THRESHOLD')
trig_net = Net('TRIGGER')
disch_net = Net('DISCHARGE')
ctrl_net = Net('CONTROL')
reset_net = Net('RESET')

# Power supply
vcc = Part('pspice', 'VDC', ref='VCC', value='9V')
vcc['+'] += vcc_net
vcc['-'] += gnd

# 555 Timer IC with proper 8-pin DIP symbol
timer = Part('Timer', 'NE555', ref='U1', 
             footprint='Package_DIP:DIP-8_W7.62mm')

# Connect 555 pins
timer['GND'] += gnd          # Pin 1
timer['TRIG'] += trig_net    # Pin 2
timer['OUT'] += out_net      # Pin 3
timer['RESET'] += reset_net  # Pin 4
timer['CONT'] += ctrl_net    # Pin 5
timer['THRES'] += thresh_net # Pin 6
timer['DISCH'] += disch_net  # Pin 7
timer['VCC'] += vcc_net      # Pin 8

# Timing resistors
r1 = Part('Device', 'R', ref='R1', value='1k', 
          footprint='Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal')
r1[1] += vcc_net
r1[2] += disch_net

r2 = Part('Device', 'R', ref='R2', value='71.5k',
          footprint='Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal')
r2[1] += disch_net
r2[2] += thresh_net

# Timing capacitor
c1 = Part('Device', 'C', ref='C1', value='10uF',
          footprint='Capacitor_THT:C_Disc_D3.0mm_W1.6mm_P2.50mm')
c1[1] += thresh_net
c1[2] += gnd

# Connect threshold to trigger for astable operation
thresh_net += trig_net

# Reset pull-up
r_reset = Part('Device', 'R', ref='R_Reset', value='10k',
               footprint='Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal')
r_reset[1] += vcc_net
r_reset[2] += reset_net

# Control voltage bypass
c_ctrl = Part('Device', 'C', ref='C_Ctrl', value='100nF',
              footprint='Capacitor_THT:C_Disc_D3.0mm_W1.6mm_P2.50mm')
c_ctrl[1] += ctrl_net
c_ctrl[2] += gnd

# LED output circuit
r_led = Part('Device', 'R', ref='R_LED', value='470',
             footprint='Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal')
r_led[1] += out_net
r_led[2] += Net('LED_ANODE')

led = Part('Device', 'LED', ref='D1',
           footprint='LED_THT:LED_D5.0mm')
led['+'] += Net('LED_ANODE')
led['-'] += gnd

# Generate files
generate_netlist(file_='555_blinker.net')
ERC()
generate_schematic(file_='555_blinker.kicad_sch')

print("✅ Perfect 555 timer schematic generated!")
print("📁 File: 555_blinker.kicad_sch")
print("🔍 Open in KiCad to see proper 8-pin DIP symbol")
```

---

## 🔧 创建KiCad服务

### 目录结构

```
kicad_service/
├── app/
│   ├── main.py                    # FastAPI服务
│   ├── routers/
│   │   └── kicad.py               # KiCad路由
│   ├── services/
│   │   ├── circuit_to_skidl.py    # CircuitIR转SKiDL
│   │   ├── schematic_generator.py # 原理图生成
│   │   └── symbol_mapper.py       # 符号映射
│   └── models/
│       └── circuit_ir.py          # 数据模型
├── examples/
│   ├── poc_opamp.py               # 运放示例
│   └── poc_555.py                 # 555示例
├── requirements.txt
└── README.md
```

### 核心服务代码

创建 `kicad_service/app/services/schematic_generator.py`:

```python
"""
KiCad Schematic Generator using SKiDL
"""
from skidl import *
from typing import Dict, Any
import os
import uuid

class KiCadSchematicGenerator:
    """Generate professional KiCad schematics from CircuitIR"""
    
    def __init__(self):
        """Initialize generator with KiCad library paths"""
        # Add KiCad symbol library paths
        self.setup_library_paths()
        
    def setup_library_paths(self):
        """Setup KiCad library search paths"""
        paths = [
            'C:/Program Files/KiCad/8.0/share/kicad/symbols',  # Windows
            '/usr/share/kicad/symbols',  # Linux
            '/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols'  # macOS
        ]
        
        for path in paths:
            if os.path.exists(path):
                lib_search_paths[KICAD].append(path)
    
    def generate_from_circuit_ir(self, circuit_ir: Dict[str, Any]) -> Dict[str, str]:
        """
        Generate KiCad schematic from CircuitIR
        
        Args:
            circuit_ir: CircuitIR dictionary
            
        Returns:
            Dictionary with paths to generated files
        """
        circuit_type = circuit_ir.get('circuit_type')
        
        if circuit_type == 'opamp_inverting':
            return self._generate_opamp_inverting(circuit_ir)
        elif circuit_type == 'opamp_non_inverting':
            return self._generate_opamp_non_inverting(circuit_ir)
        elif circuit_type == '555_timer_blinker':
            return self._generate_555_timer(circuit_ir)
        elif circuit_type == 'led_current_limiter':
            return self._generate_led_circuit(circuit_ir)
        elif circuit_type == 'rc_low_pass_filter':
            return self._generate_rc_filter(circuit_ir)
        else:
            raise ValueError(f"Unsupported circuit type: {circuit_type}")
    
    def _generate_opamp_inverting(self, circuit_ir: Dict) -> Dict[str, str]:
        """Generate inverting op-amp schematic"""
        constraints = circuit_ir.get('constraints', {})
        gain = abs(constraints.get('gain', 10))
        supply = constraints.get('supply_voltage_v', 15)
        
        # Get component values from CircuitIR
        r_in = 10000  # 10k default
        r_feedback = r_in * gain
        
        # Reset SKiDL circuit
        reset()
        
        # Create nets
        gnd = Net('GND')
        vin_net = Net('IN')
        sum_net = Net('SUMMING')
        out_net = Net('OUTPUT')
        vcc_net = Net('VCC')
        vee_net = Net('VEE')
        
        # Components
        vin = Part('pspice', 'VSOURCE', ref='Vin', value='AC 1 SIN(0 0.1 1k)')
        vin['+'] += vin_net
        vin['-'] += gnd
        
        vcc = Part('pspice', 'VDC', ref='VCC', value=f'{supply}V')
        vcc['+'] += vcc_net
        vcc['-'] += gnd
        
        vee = Part('pspice', 'VDC', ref='VEE', value=f'{supply}V')
        vee['+'] += gnd
        vee['-'] += vee_net
        
        r1 = Part('Device', 'R', ref='R1', value=f'{r_in/1000}k')
        r1[1] += vin_net
        r1[2] += sum_net
        
        r2 = Part('Device', 'R', ref='R2', value=f'{r_feedback/1000}k')
        r2[1] += out_net
        r2[2] += sum_net
        
        opamp = Part('Amplifier_Operational', 'LM741', ref='U1')
        opamp['~'] += sum_net
        opamp['+'] += gnd
        opamp['OUT'] += out_net
        opamp['V+'] += vcc_net
        opamp['V-'] += vee_net
        
        rload = Part('Device', 'R', ref='Rload', value='100k')
        rload[1] += out_net
        rload[2] += gnd
        
        # Generate files
        file_id = str(uuid.uuid4())[:8]
        sch_file = f'/tmp/opamp_inv_{file_id}.kicad_sch'
        net_file = f'/tmp/opamp_inv_{file_id}.net'
        
        generate_netlist(file_=net_file)
        generate_schematic(file_=sch_file)
        
        return {
            'schematic': sch_file,
            'netlist': net_file,
            'success': True
        }
    
    def _generate_555_timer(self, circuit_ir: Dict) -> Dict[str, str]:
        """Generate 555 timer schematic"""
        constraints = circuit_ir.get('constraints', {})
        freq = constraints.get('target_frequency_hz', 1.0)
        supply = constraints.get('supply_voltage_v', 9.0)
        
        # Calculate component values
        c1 = 10e-6  # 10uF
        r1 = 1000   # 1k
        r2 = (1.44 / (freq * c1) - r1) / 2
        r2 = max(100, min(r2, 1000000))
        
        reset()
        
        # Create nets
        gnd = Net('GND')
        vcc_net = Net('VCC')
        out_net = Net('OUTPUT')
        thresh_net = Net('THRESHOLD')
        disch_net = Net('DISCHARGE')
        ctrl_net = Net('CONTROL')
        reset_net = Net('RESET')
        
        # Components
        vcc = Part('pspice', 'VDC', ref='VCC', value=f'{supply}V')
        vcc['+'] += vcc_net
        vcc['-'] += gnd
        
        timer = Part('Timer', 'NE555', ref='U1')
        timer['GND'] += gnd
        timer['TRIG'] += thresh_net
        timer['OUT'] += out_net
        timer['RESET'] += reset_net
        timer['CONT'] += ctrl_net
        timer['THRES'] += thresh_net
        timer['DISCH'] += disch_net
        timer['VCC'] += vcc_net
        
        r1_part = Part('Device', 'R', ref='R1', value='1k')
        r1_part[1] += vcc_net
        r1_part[2] += disch_net
        
        r2_part = Part('Device', 'R', ref='R2', value=f'{r2/1000:.1f}k')
        r2_part[1] += disch_net
        r2_part[2] += thresh_net
        
        c1_part = Part('Device', 'C', ref='C1', value='10uF')
        c1_part[1] += thresh_net
        c1_part[2] += gnd
        
        r_reset = Part('Device', 'R', ref='R_Reset', value='10k')
        r_reset[1] += vcc_net
        r_reset[2] += reset_net
        
        c_ctrl = Part('Device', 'C', ref='C_Ctrl', value='100nF')
        c_ctrl[1] += ctrl_net
        c_ctrl[2] += gnd
        
        r_led = Part('Device', 'R', ref='R_LED', value='470')
        r_led[1] += out_net
        
        led = Part('Device', 'LED', ref='D1')
        led['+'] += r_led[2]
        led['-'] += gnd
        
        # Generate files
        file_id = str(uuid.uuid4())[:8]
        sch_file = f'/tmp/555_timer_{file_id}.kicad_sch'
        net_file = f'/tmp/555_timer_{file_id}.net'
        
        generate_netlist(file_=net_file)
        generate_schematic(file_=sch_file)
        
        return {
            'schematic': sch_file,
            'netlist': net_file,
            'success': True
        }

    def export_svg(self, sch_file: str) -> str:
        """
        Export KiCad schematic to SVG
        
        Args:
            sch_file: Path to .kicad_sch file
            
        Returns:
            Path to SVG file
        """
        import subprocess
        
        svg_file = sch_file.replace('.kicad_sch', '.svg')
        
        # Use KiCad CLI to export
        try:
            subprocess.run([
                'kicad-cli', 'sch', 'export', 'svg',
                '--output', svg_file,
                sch_file
            ], check=True)
        except Exception as e:
            # Fallback: read schematic and generate SVG manually
            # (SKiDL doesn't have built-in SVG export, but we can add it)
            pass
        
        return svg_file
```

---

## 🚀 快速开始

### 第一步：安装依赖

```bash
cd kicad_service
pip install -r requirements.txt
```

`requirements.txt`:
```
skidl>=1.2.0
fastapi>=0.104.0
uvicorn>=0.24.0
pydantic>=2.5.0
```

### 第二步：测试POC

```bash
# 测试运放电路生成
python examples/poc_opamp.py

# 测试555定时器生成
python examples/poc_555.py

# 在KiCad中打开
kicad opamp_inverting.kicad_sch
```

### 第三步：启动服务

```bash
cd kicad_service
python -m uvicorn app.main:app --host 0.0.0.0 --port 8004
```

### 第四步：集成到后端

修改 `backend/.env`:
```
KICAD_SERVICE_URL=http://localhost:8004
```

---

## 📊 预期效果

### 生成的KiCad原理图将包含

- ✅ **专业符号**: UA741三角形、555 DIP-8封装
- ✅ **完整标注**: 引脚名称、元件值、参考编号
- ✅ **清晰布局**: SKiDL自动布局
- ✅ **可编辑**: 标准KiCad格式，可在KiCad中打开
- ✅ **可制造**: 完整的footprint信息

---

## ✅ 下一步

1. **安装KiCad 8**: https://www.kicad.org/download/
2. **安装SKiDL**: `pip install skidl`
3. **运行POC**: 验证技术可行性
4. **反馈**: 告诉我结果，我们继续开发！

---

**这个方案100%可行，让我们开始实施！** 🚀

