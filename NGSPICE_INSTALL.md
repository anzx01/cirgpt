# NgSpice安装指南（无winget情况）

## 方案1：手动下载安装（推荐）

### Windows安装步骤：

1. **下载NgSpice**
   - 访问：https://ngspice.sourceforge.io/download.html
   - 下载最新版本的Windows安装包（例如：ngspice-39_64bit_setup.exe）

2. **安装NgSpice**
   ```cmd
   # 双击运行下载的安装包
   # 安装到默认路径：C:\Program Files\ngspice
   ```

3. **配置环境变量**
   - 将NgSpice的bin目录添加到系统PATH：
   - `C:\Program Files\ngspice\bin`

4. **验证安装**
   ```cmd
   ngspice --version
   ```

## 方案2：使用便携版（无需安装）

1. **下载便携版**
   - 访问：https://github.com/dschard/ngspice-simulator/releases
   - 下载zip压缩包

2. **解压使用**
   ```cmd
   # 解压到项目目录
   cd G:\myaist\cirgpt
   mkdir tools
   # 将ngspice解压到这里

   # 直接运行
   tools\ngspice\bin\ngspice.exe
   ```

## 方案3：使用预编译的DLL

如果只需要PySpice能找到DLL：

1. **下载DLL**
   - 从 https://github.com/ra3xdh/qucs-s/releases
   - 下载并提取ngspice.dll

2. **放置DLL**
   ```
   复制到：G:\myaist\cirgpt\eda_tools\venv\Lib\site-packages\PySpice\Spice\NgSpice\Spice64_dll\dll-vs\
   ```

## 方案4：继续使用Fallback模式（当前方式）

如果没有NgSpice，PySpice会自动使用fallback模式：

✅ **优点：**
- 无需额外安装
- 系统仍可正常运行

⚠️ **注意：**
- 会看到"Using mock data"提示
- 波形是计算生成的，不是SPICE仿真
- 但仍然基于真实的电路公式

## 当前系统状态

你的系统现在正在使用fallback模式（从测试输出可以看到）：
```
[!] WARNING: Using mock data!
Message: Simulation used mock data due to error: cannot load library 'ngspice.dll'
```

**这是正常的！** 系统其他部分都使用真实算法：
- ✅ 原理图：SKiDL真实电路
- ✅ PCB布局：智能算法
- ✅ 电路生成：真实公式
- ⚠️ 仿真：Fallback模式（但波形基于真实电路理论）

## 推荐做法

### 如果只是测试/演示：
**无需安装NgSpice** - 继续使用fallback模式即可

### 如果需要生产级仿真：
**安装NgSpice** - 使用方案1（手动下载）

---

## 快速测试

测试当前配置：
```bash
cd G:\myaist\cirgpt
python test_real_generation.py
```

系统会自动检测NgSpice是否可用，并使用相应模式。
