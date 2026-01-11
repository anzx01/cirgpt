# 组件树和状态管理方案设计

## 组件树结构

```
├── RootLayout                          # 根布局组件
│   ├── NavigationBar                   # 导航栏组件
│   │   ├── Logo                        # 应用Logo
│   │   ├── NavMenu                     # 导航菜单
│   │   ├── UserProfile                 # 用户资料
│   │   └── NotificationCenter          # 通知中心
│   ├── MainContent                     # 主内容区域
│   └── Footer                          # 页脚组件
├── DashboardLayout                     # 仪表板布局
│   ├── DashboardSidebar                # 仪表板侧边栏
│   ├── DashboardContent                # 仪表板内容
│   │   ├── ProjectList                 # 项目列表
│   │   ├── RecentActivity              # 最近活动
│   │   └── StatisticsCard              # 统计卡片
│   └── DashboardHeader                 # 仪表板头部
├── DesignLayout                        # 设计工作区布局
│   ├── DesignSidebar                   # 设计侧边栏
│   ├── DesignContent                   # 设计内容
│   │   ├── DesignInput                 # 自然语言输入组件
│   │   ├── ParameterForm               # 参数表单组件
│   │   └── DesignProgress              # 设计进度指示器
│   └── DesignHeader                    # 设计头部
├── ProjectLayout                       # 项目布局
│   ├── ProjectTabs                     # 项目标签页
│   ├── ProjectContent                  # 项目内容
│   └── ProjectHeader                   # 项目头部
├── SchematicPage                       # 原理图页面
│   ├── SchematicToolbar                # 原理图工具栏
│   ├── SchematicViewer                 # 交互式原理图查看器
│   │   ├── ComponentPalette            # 元件调色板
│   │   ├── ConnectionTools             # 连接工具
│   │   ├── ZoomControls                # 缩放控制
│   │   └── ComponentInspector          # 元件检查器
│   └── SchematicProperties             # 原理图属性面板
├── SimulationPage                      # 模拟结果页面
│   ├── SimulationControls              # 模拟控制
│   ├── SimulationResults               # 模拟结果图表
│   │   ├── WaveformViewer              # 波形查看器
│   │   ├── DataTable                   # 数据表格
│   │   └── ExportButton                # 导出按钮
│   └── SimulationProperties            # 模拟属性面板
├── PCBPage                             # PCB页面
│   ├── PCBToolbar                      # PCB工具栏
│   ├── PCBLayoutViewer                 # PCB布局查看器
│   │   ├── 3DViewer                    # 3D预览
│   │   ├── LayerControl                # 层控制
│   │   └── DRCResults                  # DRC结果
│   └── PCBProperties                   # PCB属性面板
├── BOMPage                             # BOM页面
│   ├── BOMToolbar                      # BOM工具栏
│   ├── BOMEditor                       # BOM编辑器
│   │   ├── BOMTable                    # BOM表格
│   │   ├── ComponentDetails            # 元件详情
│   │   └── SupplierSearch              # 供应商查询
│   └── BOMProperties                   # BOM属性面板
├── TemplatesPage                       # 模板库页面
│   ├── TemplateFilter                  # 模板筛选器
│   ├── TemplateGrid                    # 模板网格
│   └── TemplateCard                    # 模板卡片
└── ComponentsPage                      # 元件库页面
    ├── ComponentFilter                 # 元件筛选器
    ├── ComponentGrid                   # 元件网格
    └── ComponentCard                   # 元件卡片
```

## 状态管理方案

### 1. Zustand全局状态管理

```typescript
// src/store/useAppStore.ts
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface DesignProgress {
  stage: 'parsing' | 'generating' | 'simulating' | 'pcb' | 'bom' | 'complete'
  percentage: number
  message: string
}

export interface CircuitComponent {
  id: string
  type: string
  model: string
  value?: string
  footprint?: string
  color?: string
  position: { x: number; y: number }
}

export interface CircuitConnection {
  id: string
  from: { componentId: string; pinId: string }
  to: { componentId: string; pinId: string }
}

export interface CircuitDesign {
  id: string
  name: string
  description: string
  components: CircuitComponent[]
  connections: CircuitConnection[]
  createdAt: Date
  updatedAt: Date
}

export interface AppState {
  // 用户状态
  user: {
    id: string
    name: string
    email: string
  } | null
  isAuthenticated: boolean
  setUser: (user: any) => void
  logout: () => void
  
  // 设计状态
  currentDesign: CircuitDesign | null
  designs: CircuitDesign[]
  addDesign: (design: CircuitDesign) => void
  updateDesign: (design: Partial<CircuitDesign> & { id: string }) => void
  deleteDesign: (id: string) => void
  setCurrentDesign: (design: CircuitDesign | null) => void
  
  // 进度状态
  designProgress: DesignProgress
  setDesignProgress: (progress: Partial<DesignProgress>) => void
  resetDesignProgress: () => void
  
  // UI状态
  isSidebarOpen: boolean
  toggleSidebar: () => void
  activeTab: string
  setActiveTab: (tab: string) => void
}

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      // 用户状态
      user: null,
      isAuthenticated: false,
      setUser: (user) => set({ user, isAuthenticated: true }),
      logout: () => set({ user: null, isAuthenticated: false }),
      
      // 设计状态
      currentDesign: null,
      designs: [],
      addDesign: (design) => set((state) => ({ designs: [...state.designs, design] })),
      updateDesign: (updatedDesign) => set((state) => ({
        designs: state.designs.map((design) =>
          design.id === updatedDesign.id ? { ...design, ...updatedDesign } : design
        ),
        currentDesign: state.currentDesign?.id === updatedDesign.id
          ? { ...state.currentDesign, ...updatedDesign }
          : state.currentDesign
      })),
      deleteDesign: (id) => set((state) => ({
        designs: state.designs.filter((design) => design.id !== id),
        currentDesign: state.currentDesign?.id === id ? null : state.currentDesign
      })),
      setCurrentDesign: (design) => set({ currentDesign: design }),
      
      // 进度状态
      designProgress: {
        stage: 'parsing',
        percentage: 0,
        message: '开始解析设计请求'
      },
      setDesignProgress: (progress) => set((state) => ({
        designProgress: { ...state.designProgress, ...progress }
      })),
      resetDesignProgress: () => set({
        designProgress: {
          stage: 'parsing',
          percentage: 0,
          message: '开始解析设计请求'
        }
      }),
      
      // UI状态
      isSidebarOpen: true,
      toggleSidebar: () => set((state) => ({ isSidebarOpen: !state.isSidebarOpen })),
      activeTab: 'schematic',
      setActiveTab: (tab) => set({ activeTab: tab })
    }),
    {
      name: 'circuit-gpt-storage',
      partialize: (state) => ({
        user: state.user,
        isAuthenticated: state.isAuthenticated
      })
    }
  )
)
```

### 2. React Query服务器状态管理

```typescript
// src/services/designService.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL

// 获取设计列表
export const useDesigns = () => {
  return useQuery({
    queryKey: ['designs'],
    queryFn: async () => {
      const response = await axios.get(`${API_URL}/designs`)
      return response.data
    }
  })
}

// 获取单个设计
export const useDesign = (id: string) => {
  return useQuery({
    queryKey: ['design', id],
    queryFn: async () => {
      const response = await axios.get(`${API_URL}/designs/${id}`)
      return response.data
    },
    enabled: !!id
  })
}

// 创建新设计
export const useCreateDesign = () => {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (designData: any) => {
      const response = await axios.post(`${API_URL}/designs`, designData)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['designs'] })
    }
  })
}

// 更新设计
export const useUpdateDesign = () => {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: any }) => {
      const response = await axios.put(`${API_URL}/designs/${id}`, data)
      return response.data
    },
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['design', id] })
      queryClient.invalidateQueries({ queryKey: ['designs'] })
    }
  })
}

// 解析设计请求
export const useParseDesign = () => {
  return useMutation({
    mutationFn: async (inputText: string) => {
      const response = await axios.post(`${API_URL}/ai/parse`, { input_text: inputText })
      return response.data
    }
  })
}

// 获取模拟结果
export const useSimulationResults = (designId: string) => {
  return useQuery({
    queryKey: ['simulation', designId],
    queryFn: async () => {
      const response = await axios.get(`${API_URL}/designs/${designId}/simulation`)
      return response.data
    },
    enabled: !!designId
  })
}
```

## 组件状态管理示例

### 1. DesignInput组件

```typescript
// src/components/DesignInput/DesignInput.tsx
'use client'

import { useState } from 'react'
import { useParseDesign } from '@/services/designService'
import { useAppStore } from '@/store/useAppStore'
import { TextField, Button, Paper, Typography, Box, CircularProgress } from '@mui/material'

const DesignInput = () => {
  const [inputText, setInputText] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  
  const parseDesign = useParseDesign()
  const { setDesignProgress } = useAppStore()
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!inputText.trim()) return
    
    setIsSubmitting(true)
    setDesignProgress({
      stage: 'parsing',
      percentage: 10,
      message: '正在解析设计请求'
    })
    
    try {
      const result = await parseDesign.mutateAsync(inputText)
      // 处理解析结果
    } catch (error) {
      // 处理错误
    } finally {
      setIsSubmitting(false)
    }
  }
  
  return (
    <Paper elevation={3} sx={{ p: 3, mb: 3 }}>
      <Typography variant="h5" gutterBottom>
        输入电路设计需求
      </Typography>
      <Box component="form" onSubmit={handleSubmit} sx={{ mt: 2 }}>
        <TextField
          fullWidth
          label="自然语言描述"
          multiline
          rows={4}
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          placeholder="例如：设计一个使用Arduino UNO的LED闪烁电路，电阻220欧，LED红色"
          sx={{ mb: 2 }}
          disabled={isSubmitting}
        />
        <Button
          type="submit"
          variant="contained"
          color="primary"
          fullWidth
          disabled={isSubmitting || !inputText.trim()}
          startIcon={isSubmitting ? <CircularProgress size={20} color="inherit" /> : null}
        >
          {isSubmitting ? '解析中...' : '开始设计'}
        </Button>
      </Box>
    </Paper>
  )
}

export default DesignInput
```

### 2. DesignProgress组件

```typescript
// src/components/DesignProgress/DesignProgress.tsx
'use client'

import { useAppStore } from '@/store/useAppStore'
import { LinearProgress, Paper, Typography, Box, Chip } from '@mui/material'

const DesignProgress = () => {
  const { designProgress } = useAppStore()
  
  const stageLabels: Record<string, string> = {
    parsing: '解析请求',
    generating: '生成网表',
    simulating: '电路模拟',
    pcb: 'PCB布局',
    bom: '生成BOM',
    complete: '完成'
  }
  
  const stageColors: Record<string, string> = {
    parsing: 'primary',
    generating: 'info',
    simulating: 'success',
    pcb: 'warning',
    bom: 'error',
    complete: 'success'
  }
  
  return (
    <Paper elevation={3} sx={{ p: 3, mb: 3 }}>
      <Typography variant="h5" gutterBottom>
        设计进度
      </Typography>
      <Box sx={{ mb: 2 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
          <Typography variant="body2" color="text.secondary">
            {stageLabels[designProgress.stage]}
          </Typography>
          <Chip
            label={stageLabels[designProgress.stage]}
            color={stageColors[designProgress.stage] as any}
            size="small"
          />
        </Box>
        <LinearProgress
          variant="determinate"
          value={designProgress.percentage}
          sx={{ height: 10, borderRadius: 5 }}
        />
      </Box>
      <Typography variant="body2" color="text.secondary">
        {designProgress.message}
      </Typography>
    </Paper>
  )
}

export default DesignProgress
```

## 状态管理最佳实践

1. **分离状态类型**：
   - 使用Zustand管理客户端状态（UI状态、用户认证、本地设计数据）
   - 使用React Query管理服务器状态（API数据、异步操作）

2. **状态持久化**：
   - 使用Zustand的persist中间件持久化用户认证状态
   - 使用localStorage或IndexedDB持久化离线编辑数据

3. **状态更新优化**：
   - 使用React Query的缓存和失效机制优化数据获取
   - 使用Zustand的浅比较减少不必要的重渲染

4. **错误处理**：
   - 在React Query中统一处理API错误
   - 在Zustand中管理错误状态和用户反馈

5. **组件复用**：
   - 将状态逻辑与UI组件分离
   - 使用自定义Hook封装复杂的状态逻辑

6. **性能优化**：
   - 使用React.memo优化组件性能
   - 使用QueryClient的预取功能提升用户体验

这个组件树和状态管理方案为我们的电路设计应用提供了一个坚实的架构基础，支持所有核心功能模块，并确保了良好的性能和用户体验。