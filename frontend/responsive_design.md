# 响应式布局断点设计

## 1. 概述

响应式布局是确保电路设计系统在各种设备上都能提供良好用户体验的关键。本设计方案定义了完整的断点系统、布局策略和组件级别的响应式设计指南，确保应用在从手机到桌面显示器的所有屏幕尺寸上都能正常工作。

## 2. 断点设计原则

1. **基于设备优先**：针对主要设备类型（手机、平板、桌面）设计断点
2. **内容驱动**：根据内容的可读性和可用性确定断点位置
3. **渐进增强**：从最小屏幕开始设计，逐步增强到更大屏幕
4. **保持一致性**：在整个应用中使用统一的断点系统
5. **性能考虑**：避免过多断点导致的样式复杂性

## 3. 断点值定义

### 3.1 Material-UI断点集成

```typescript
// src/theme/breakpoints.ts
import { createTheme } from '@mui/material/styles'

// 扩展Material-UI默认断点
const theme = createTheme({
  breakpoints: {
    values: {
      xs: 0,      // 手机 (0-599px)
      sm: 600,    // 小平板 (600-959px)
      md: 960,    // 平板 (960-1279px)
      lg: 1280,   // 小桌面 (1280-1919px)
      xl: 1920    // 大桌面 (1920px+)
    }
  }
})

export default theme
```

### 3.2 自定义断点扩展

```typescript
// src/utils/responsive.ts
export const breakpoints = {
  xs: '(max-width: 599px)',    // 手机
  sm: '(min-width: 600px) and (max-width: 959px)',  // 小平板
  md: '(min-width: 960px) and (max-width: 1279px)', // 平板
  lg: '(min-width: 1280px) and (max-width: 1919px)', // 小桌面
  xl: '(min-width: 1920px)',   // 大桌面
  
  // 方向断点
  portrait: '(orientation: portrait)',
  landscape: '(orientation: landscape)',
  
  // 高分辨率屏幕
  highDpi: '(-webkit-min-device-pixel-ratio: 2), (min-resolution: 192dpi)'
}

// 媒体查询生成器
export const mediaQuery = (breakpoint: keyof typeof breakpoints) => {
  return `@media ${breakpoints[breakpoint]}`
}
```

## 4. 布局策略

### 4.1 手机布局 (xs, 0-599px)

- **导航**：使用汉堡菜单，导航项折叠
- **内容**：单列布局，垂直排列
- **工具栏**：简化工具栏，常用功能优先
- **侧边栏**：折叠为抽屉式菜单
- **字体大小**：减小基础字体大小，确保可读性

```typescript
// src/components/DesignSidebar/DesignSidebar.tsx
'use client'

import { Drawer, List, ListItem, ListItemText, IconButton } from '@mui/material'
import { Menu, ChevronLeft } from '@mui/icons-material'
import { useAppStore } from '@/store/useAppStore'

const DesignSidebar = () => {
  const { isSidebarOpen, toggleSidebar } = useAppStore()

  return (
    <>
      {/* 移动端抽屉 */}
      <Drawer
        variant="temporary"
        anchor="left"
        open={isSidebarOpen}
        onClose={toggleSidebar}
        sx={{
          '& .MuiDrawer-paper': {
            width: 240,
            boxSizing: 'border-box'
          }
        }}
      >
        <div sx={{ display: 'flex', justifyContent: 'flex-end', p: 1 }}>
          <IconButton onClick={toggleSidebar}>
            <ChevronLeft />
          </IconButton>
        </div>
        {/* 侧边栏内容 */}
        <List>
          <ListItem button>
            <ListItemText primary="设计参数" />
          </ListItem>
          <ListItem button>
            <ListItemText primary="元件库" />
          </ListItem>
          {/* 更多菜单项 */}
        </List>
      </Drawer>

      {/* 桌面端永久侧边栏 */}
      <div
        sx={{
          width: 240,
          display: { xs: 'none', lg: 'block' }
        }}
      >
        {/* 侧边栏内容 */}
      </div>
    </>
  )
}

export default DesignSidebar
```

### 4.2 小平板布局 (sm, 600-959px)

- **导航**：部分导航项可显示在顶部
- **内容**：双列布局（如果空间允许）
- **工具栏**：显示更多功能按钮
- **侧边栏**：可选择折叠或显示
- **字体大小**：稍微增大字体

```typescript
// src/components/DesignLayout/DesignLayout.tsx
'use client'

import { Box, Toolbar } from '@mui/material'
import DesignSidebar from '@/components/DesignSidebar/DesignSidebar'
import DesignContent from '@/components/DesignContent/DesignContent'

export default function DesignLayout({ children }: { children: React.ReactNode }) {
  return (
    <Box sx={{ display: 'flex' }}>
      {/* 侧边栏在小平板上可选择折叠 */}
      <DesignSidebar />
      <Box component="main" sx={{ flexGrow: 1, p: 3 }}>
        <Toolbar />
        {/* 在小平板上使用更紧凑的布局 */}
        <Box sx={{ 
          display: { xs: 'block', sm: 'grid', md: 'grid' },
          gridTemplateColumns: { sm: '1fr 1fr', md: '2fr 1fr' },
          gap: 2 
        }}>
          <DesignContent />
          {children}
        </Box>
      </Box>
    </Box>
  )
}
```

### 4.3 平板布局 (md, 960-1279px)

- **导航**：完整顶部导航
- **内容**：灵活的网格布局
- **工具栏**：完整功能集
- **侧边栏**：永久显示（如果内容不拥挤）
- **字体大小**：标准字体大小

### 4.4 小桌面布局 (lg, 1280-1919px)

- **导航**：完整顶部导航 + 侧边栏
- **内容**：多列网格布局
- **工具栏**：完整功能集 + 快捷键提示
- **侧边栏**：永久显示
- **工作区**：可分割的多面板布局

```typescript
// src/components/SchematicViewer/SchematicViewer.tsx
'use client'

import { Box, SplitPane } from '@mui/material'
import ComponentPalette from '@/components/ComponentPalette/ComponentPalette'
import ConnectionTools from '@/components/ConnectionTools/ConnectionTools'
import ComponentInspector from '@/components/ComponentInspector/ComponentInspector'

export default function SchematicViewer() {
  return (
    <Box sx={{ display: 'flex', height: 'calc(100vh - 200px)' }}>
      {/* 左侧面板：元件调色板 */}
      <Box 
        sx={{
          width: { xs: '100%', lg: '250px' },
          display: { xs: 'none', lg: 'block' }
        }}
      >
        <ComponentPalette />
      </Box>

      {/* 主工作区 */}
      <Box sx={{ flexGrow: 1, position: 'relative' }}>
        {/* 原理图画布 */}
      </Box>

      {/* 右侧面板：属性检查器 */}
      <Box 
        sx={{
          width: { xs: '100%', lg: '300px' },
          display: { xs: 'none', lg: 'block' }
        }}
      >
        <ComponentInspector />
      </Box>
    </Box>
  )
}
```

### 4.5 大桌面布局 (xl, 1920px+)

- **导航**：完整顶部导航 + 侧边栏
- **内容**：多列网格布局（3列或更多）
- **工具栏**：完整功能集 + 高级选项
- **工作区**：可定制的多面板布局
- **可视化**：更高分辨率的渲染质量

```typescript
// src/components/PCBLayoutViewer/PCBLayoutViewer.tsx
'use client'

import { Box } from '@mui/material'
import { useTheme } from '@mui/material/styles'
import { useMediaQuery } from '@mui/material'

export default function PCBLayoutViewer() {
  const theme = useTheme()
  const isLargeScreen = useMediaQuery(theme.breakpoints.up('xl'))

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* PCB 3D视图：在大屏幕上使用更高分辨率 */}
      <Box 
        sx={{
          flexGrow: 1,
          position: 'relative',
          // 大屏幕上使用更高分辨率
          '& canvas': {
            resolution: isLargeScreen ? 'high' : 'medium'
          }
        }}
      >
        {/* 3D渲染画布 */}
      </Box>

      {/* 层控制面板 */}
      <Box 
        sx={{
          height: { xs: '100px', xl: '150px' },
          overflowX: 'auto'
        }}
      >
        {/* 层控制 */}
      </Box>
    </Box>
  )
}
```

## 5. 核心组件响应式设计

### 5.1 DesignInput组件

```typescript
// src/components/DesignInput/DesignInput.tsx
'use client'

import { TextField, Button, Paper, Typography, Box, Grid } from '@mui/material'

export default function DesignInput() {
  const [inputText, setInputText] = useState('')

  return (
    <Paper elevation={3} sx={{ p: { xs: 2, md: 3 }, mb: 3 }}>
      <Typography variant={{ xs: 'h6', md: 'h5' }} gutterBottom>
        输入电路设计需求
      </Typography>
      
      <Box component="form" sx={{ mt: 2 }}>
        {/* 在移动设备上使用单列布局，桌面设备上使用双列 */}
        <Grid container spacing={2}>
          <Grid item xs={12} md={9}>
            <TextField
              fullWidth
              label="自然语言描述"
              multiline
              rows={{ xs: 3, md: 4 }}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder="例如：设计一个使用Arduino UNO的LED闪烁电路，电阻220欧，LED红色"
            />
          </Grid>
          <Grid item xs={12} md={3} sx={{ display: 'flex', alignItems: 'flex-end' }}>
            <Button
              type="submit"
              variant="contained"
              color="primary"
              fullWidth
              sx={{ height: { xs: 'auto', md: 56 } }}
              disabled={!inputText.trim()}
            >
              开始设计
            </Button>
          </Grid>
        </Grid>
      </Box>
    </Paper>
  )
}
```

### 5.2 SchematicViewer组件

```typescript
// src/components/SchematicViewer/SchematicViewer.tsx
'use client'

import { Box, IconButton, Tooltip } from '@mui/material'
import { ZoomIn, ZoomOut, FitScreen, RotateLeft, RotateRight } from '@mui/icons-material'

export default function SchematicViewer() {
  return (
    <Box sx={{ position: 'relative', width: '100%', height: '600px', border: 1, borderColor: 'divider' }}>
      {/* 原理图画布 */}
      <Box sx={{ width: '100%', height: '100%', overflow: 'hidden' }}>
        {/* SVG.js渲染区域 */}
      </Box>

      {/* 缩放控制：在移动设备上浮动，桌面设备上固定在角落 */}
      <Box
        sx={{
          position: 'absolute',
          bottom: 16,
          right: 16,
          display: 'flex',
          gap: 1,
          backgroundColor: 'background.paper',
          borderRadius: 1,
          p: 1,
          boxShadow: 1,
          // 移动设备上使用更大的按钮
          '& .MuiIconButton-root': {
            fontSize: { xs: 'large', md: 'medium' }
          }
        }}
      >
        <Tooltip title="放大">
          <IconButton size="small">
            <ZoomIn />
          </IconButton>
        </Tooltip>
        <Tooltip title="缩小">
          <IconButton size="small">
            <ZoomOut />
          </IconButton>
        </Tooltip>
        <Tooltip title="适应屏幕">
          <IconButton size="small">
            <FitScreen />
          </IconButton>
        </Tooltip>
        {/* 在大屏幕上显示更多控制按钮 */}
        <Box sx={{ display: { xs: 'none', md: 'flex' } }}>
          <Tooltip title="左旋">
            <IconButton size="small">
              <RotateLeft />
            </IconButton>
          </Tooltip>
          <Tooltip title="右旋">
            <IconButton size="small">
              <RotateRight />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>
    </Box>
  )
}
```

### 5.3 SimulationResults组件

```typescript
// src/components/SimulationResults/SimulationResults.tsx
'use client'

import { Box, Tabs, Tab, Paper, Typography } from '@mui/material'
import WaveformViewer from './WaveformViewer'
import DataTable from './DataTable'

export default function SimulationResults() {
  const [value, setValue] = useState(0)

  const handleChange = (_event: React.SyntheticEvent, newValue: number) => {
    setValue(newValue)
  }

  return (
    <Paper elevation={3} sx={{ p: 3, mb: 3 }}>
      <Typography variant="h5" gutterBottom>
        模拟结果
      </Typography>

      {/* 在移动设备上使用更紧凑的标签页 */}
      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
        <Tabs 
          value={value} 
          onChange={handleChange}
          variant={{ xs: 'scrollable', md: 'fullWidth' }}
          scrollButtons="auto"
        >
          <Tab label="波形图" />
          <Tab label="数据表" />
          <Tab label="参数" />
        </Tabs>
      </Box>

      {/* 波形图：在移动设备上使用更小的高度 */}
      <Box sx={{ height: { xs: 300, md: 500 } }}>
        {value === 0 && <WaveformViewer />}
        {value === 1 && <DataTable />}
        {value === 2 && <SimulationParameters />}
      </Box>
    </Paper>
  )
}
```

## 6. 响应式设计工具和辅助函数

### 6.1 响应式工具函数

```typescript
// src/utils/responsive.ts

// 根据屏幕尺寸返回不同值
export function responsiveValue<T>(
  xs: T,
  sm?: T,
  md?: T,
  lg?: T,
  xl?: T
): T {
  const width = window.innerWidth
  
  if (width >= 1920 && xl !== undefined) return xl
  if (width >= 1280 && lg !== undefined) return lg
  if (width >= 960 && md !== undefined) return md
  if (width >= 600 && sm !== undefined) return sm
  return xs
}

// 获取当前屏幕尺寸
export function getScreenSize(): 'xs' | 'sm' | 'md' | 'lg' | 'xl' {
  const width = window.innerWidth
  
  if (width >= 1920) return 'xl'
  if (width >= 1280) return 'lg'
  if (width >= 960) return 'md'
  if (width >= 600) return 'sm'
  return 'xs'
}

// 响应式样式生成器
export function responsiveStyle<T extends Record<string, any>>(
  styles: {
    xs?: T
    sm?: T
    md?: T
    lg?: T
    xl?: T
  }
): T {
  const size = getScreenSize()
  return { ...styles.xs, ...styles[size] } as T
}
```

### 6.2 响应式Hook

```typescript
// src/hooks/useResponsive.ts
'use client'

import { useEffect, useState } from 'react'
import { getScreenSize, responsiveValue } from '@/utils/responsive'

export function useResponsive() {
  const [screenSize, setScreenSize] = useState<'xs' | 'sm' | 'md' | 'lg' | 'xl'>(() => getScreenSize())

  useEffect(() => {
    const handleResize = () => {
      setScreenSize(getScreenSize())
    }

    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  return {
    screenSize,
    isXs: screenSize === 'xs',
    isSm: screenSize === 'sm',
    isMd: screenSize === 'md',
    isLg: screenSize === 'lg',
    isXl: screenSize === 'xl',
    isMobile: screenSize === 'xs' || screenSize === 'sm',
    isTablet: screenSize === 'md',
    isDesktop: screenSize === 'lg' || screenSize === 'xl',
    responsiveValue,
    getScreenSize
  }
}
```

## 7. 性能优化

### 7.1 延迟加载组件

```typescript
// src/components/HeavyComponent/HeavyComponent.tsx
'use client'

import { Suspense } from 'react'
import { Box, CircularProgress } from '@mui/material'
import { useResponsive } from '@/hooks/useResponsive'

// 动态导入组件
const HeavyComponentImpl = React.lazy(() => import('./HeavyComponentImpl'))

export default function HeavyComponent() {
  const { isMobile } = useResponsive()

  // 在移动设备上不加载或简化组件
  if (isMobile) {
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        <Typography variant="body2" color="text.secondary">
          此功能仅在桌面设备上可用
        </Typography>
      </Box>
    )
  }

  return (
    <Suspense fallback={<CircularProgress />}>
      <HeavyComponentImpl />
    </Suspense>
  )
}
```

### 7.2 条件渲染

```typescript
// src/components/AdvancedTools/AdvancedTools.tsx
'use client'

import { Box, Typography, Divider } from '@mui/material'
import AdvancedSimulation from './AdvancedSimulation'
import AdvancedRouting from './AdvancedRouting'
import { useResponsive } from '@/hooks/useResponsive'

export default function AdvancedTools() {
  const { isDesktop } = useResponsive()

  // 仅在桌面设备上显示高级工具
  if (!isDesktop) return null

  return (
    <Box sx={{ mt: 3 }}>
      <Typography variant="h6" gutterBottom>
        高级工具
      </Typography>
      <Divider sx={{ mb: 2 }} />
      <AdvancedSimulation />
      <AdvancedRouting />
    </Box>
  )
}
```

## 8. 测试和调试

### 8.1 测试策略

1. **设备测试**：在实际设备上测试应用
2. **浏览器开发工具**：使用Chrome DevTools的设备模拟器
3. **断点测试**：针对每个断点单独测试
4. **交互测试**：确保所有交互在不同尺寸下正常工作
5. **性能测试**：检查不同设备上的加载时间

### 8.2 调试技巧

```typescript
// src/utils/debug.ts
// 响应式调试工具
export function debugResponsive() {
  const size = getScreenSize()
  const width = window.innerWidth
  
  console.log(`Current screen size: ${size} (${width}px)`)
  
  // 在页面上显示当前断点（仅开发环境）
  if (process.env.NODE_ENV === 'development') {
    let debugElement = document.getElementById('responsive-debug')
    
    if (!debugElement) {
      debugElement = document.createElement('div')
      debugElement.id = 'responsive-debug'
      debugElement.style.cssText = `
        position: fixed;
        top: 10px;
        right: 10px;
        background: rgba(0, 0, 0, 0.7);
        color: white;
        padding: 5px 10px;
        border-radius: 4px;
        font-family: monospace;
        z-index: 9999;
      `
      document.body.appendChild(debugElement)
    }
    
    debugElement.textContent = `${size} (${width}px)`
  }
}
```

## 9. 总结

本响应式布局设计方案提供了完整的断点系统、布局策略和组件级别的响应式设计指南，确保电路设计系统在各种设备上都能提供良好的用户体验。通过与Material-UI的断点系统集成、自定义响应式工具和性能优化策略，我们实现了一个既美观又实用的响应式应用。

关键成果包括：

1. 定义了基于设备的断点系统
2. 为不同屏幕尺寸制定了布局策略
3. 为核心组件设计了响应式实现
4. 提供了响应式工具和辅助函数
5. 考虑了性能优化和测试策略

这个设计确保了电路设计系统在从手机到桌面显示器的所有设备上都能提供一致、易用的体验。