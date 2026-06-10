"""
测试SKiDL符号库配置
"""
import os
import sys

# 设置符号库路径
symbol_dir = os.path.abspath('symbols')
os.environ['KICAD_SYMBOL_DIR'] = symbol_dir
os.environ['KICAD8_SYMBOL_DIR'] = symbol_dir

print(f"Symbol dir: {symbol_dir}")
print(f"Exists: {os.path.exists(symbol_dir)}")

# 导入SKiDL
from skidl import *

# 添加到搜索路径
lib_search_paths[KICAD].append(symbol_dir)
print(f"Search paths: {lib_search_paths[KICAD]}")

# 测试创建元件
try:
    print("\n=== Testing LED ===")
    led = Part('Device', 'LED', dest=TEMPLATE)
    print("✅ LED created")
except Exception as e:
    print(f"❌ LED failed: {e}")

try:
    print("\n=== Testing Resistor ===")
    r = Part('Device', 'R', dest=TEMPLATE)
    print("✅ Resistor created")
except Exception as e:
    print(f"❌ Resistor failed: {e}")

try:
    print("\n=== Testing Power ===")
    vcc = Part('power', 'VCC', dest=TEMPLATE)
    print("✅ VCC created")
except Exception as e:
    print(f"❌ VCC failed: {e}")

print("\n=== Test complete ===")
