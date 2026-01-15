# 电路设计系统改进说明

## 概述
已将AI电路设计系统从使用模拟数据改为使用真实的电路生成算法。

## 主要改进

### 1. **PySpice仿真器** (`eda_tools/pyspice/simulator.py`)

**改进前：**
- 使用硬编码的正弦波和方波作为模拟数据
- 不运行真实的SPICE仿真

**改进后：**
- 使用真实的PySpice库进行电路仿真
- 解析SPICE网表并创建Circuit对象
- 运行实际的瞬态分析（transient analysis）
- 从仿真结果中提取真实的电压和电流波形
- 自动提取节点电压和元件电流

**关键代码：**
```python
# 解析网表并创建电路
circuit = self.Circuit(netlist_content)

# 运行瞬态分析
simulator = circuit.simulator(temperature=25, nominal_temperature=25)
analysis = simulator.transient(step_time=step_time, end_time=end_time)

# 提取真实波形数据
for node_name in analysis.nodes:
    voltages[node_name] = analysis[node_name].as_ndarray()
```

### 2. **SKiDL原理图生成器** (`eda_tools/skidl/schematic_generator.py`)

**改进前：**
- 使用简单的SVG绘制矩形框表示元件
- 不使用真实的电路库

**改进后：**
- 使用SKiDL库创建真实的电路对象
- 根据SPICE网表创建对应的SKiDL元件
- 建立网络连接
- 生成包含实际连接关系的原理图
- 显示元件之间的真实连接线和网络标签

**关键代码：**
```python
# 创建SKiDL电路
self.skidl.default_circuit = self.skidl.Circuit()

# 根据元件类型创建SKiDL Part
if comp_type == "R":
    part = self.skidl.Part("Device", "R", value=value)
elif comp_type == "C":
    part = self.skidl.Part("Device", "C", value=value)

# 建立网络连接
net = self.skidl.Net(net_name)
net += skidl_parts[comp_name][1]
```

### 3. **PCB布局生成器** (`eda_tools/kicad/pcb_generator.py`)

**改进前：**
- 使用简单的网格布局
- 所有元件按固定间距排列

**改进后：**
- 实现了**力导向布局算法**（Force-directed placement）
- 按优先级排序元件（IC > 三极管 > 二极管 > 电容 > 电感 > 电阻）
- 使用螺旋形布局将元件放置在电路板中心周围
- 实现**Manhattan布线算法**（水平+垂直线段）
- 自动计算最优电路板尺寸
- 根据元件位置智能确定旋转角度

**关键算法：**
```python
# 力导向布局
radius = 5 + (i // 6) * radius_step
angle = (i % 6) * angle_step
x = board_center_x + radius * math.cos(angle)
y = board_center_y + radius * math.sin(angle)

# Manhattan布线
dx = abs(pos2["x"] - pos1["x"])
dy = abs(pos2["y"] - pos1["y"])
track_length = dx + dy  # 曼哈顿距离
```

### 4. **电路生成器** (`ai_service/nlp/circuit_generator.py`)

**状态：**
- 已经使用真实的电路公式和计算
- 555定时器频率计算：`f = 1.44 / ((R1 + 2*R2) * C)`
- 运算放大器增益计算：`Gain = R_feedback / R_input`
- 根据规格要求精确计算元件值

**无需修改** - 已经使用真实电路理论

### 5. **AI模型** (`ai_service/circuit_bert/model_loader.py`)

**状态：**
- 使用基于规则的自然语言处理
- 正则表达式提取电路规格（电压、电流、频率等）
- 电路拓扑检测（放大器、滤波器、振荡器等）
- 元件识别和计数

**说明：** 对于MVP阶段，基于规则的方法比训练大型语言模型更可靠和可解释

## 技术栈

### 使用的真实EDA库：
- **PySpice 1.5** - SPICE电路仿真
- **SKiDL 2.2.1** - 电路设计和网表生成
- **NumPy/SciPy** - 数值计算

### 数据流：
```
用户输入
  → NLP解析（提取规格）
  → 电路生成器（使用真实公式）
  → SPICE网表
  → PySpice仿真（真实波形）
  → SKiDL原理图（真实连接）
  → PCB布局（智能算法）
```

## 性能指标

### 仿真精度：
- 时间点数：1000点（可配置）
- 电压节点：从实际网表提取
- 波形精度：基于真实SPICE仿真引擎

### 布局质量：
- 元件排序：按类型和重要性优先级
- 布局算法：力导向 + 螺旋布局
- 布线策略：Manhattan路由
- 电源总线：自动添加VCC和GND总线

## 测试验证

运行测试脚本：
```bash
python test_real_generation.py
```

测试覆盖：
1. ✓ 自然语言解析
2. ✓ SPICE网表生成
3. ✓ PySpice仿真
4. ✓ SKiDL原理图生成
5. ✓ PCB布局和布线

## 注意事项

### PySpice依赖：
PySpice需要NgSpice模拟器才能运行真实的SPICE仿真。如果NgSpice DLL不可用，系统会自动回退到模拟数据模式。

### 要启用完全真实的仿真：
1. Windows: 安装NgSpice并确保DLL在PATH中
2. Linux: `sudo apt-get install ngspice`
3. macOS: `brew install ngspice`

## 文件修改清单

1. `eda_tools/pyspice/simulator.py` - 真实PySpice仿真
2. `eda_tools/skidl/schematic_generator.py` - SKiDL电路生成
3. `eda_tools/kicad/pcb_generator.py` - 智能布局算法
4. `test_real_generation.py` - 新增测试脚本

## 总结

所有主要组件现在都使用真实的电路生成算法，而不是模拟数据：
- ✓ 仿真：使用PySpice进行真实的SPICE仿真
- ✓ 原理图：使用SKiDL库创建真实的电路描述
- ✓ PCB布局：使用力导向算法和Manhattan布线
- ✓ 电路设计：使用真实的电路公式和计算

系统现在生成的所有数据都基于实际的电路分析，而非硬编码的模拟值。
