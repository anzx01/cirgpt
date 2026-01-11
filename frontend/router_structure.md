# Next.js App Router路由结构设计

## 根目录结构

```
/app
├── layout.tsx              # 根布局组件（包含导航栏和页脚）
├── page.tsx               # 首页
├── api/                   # API路由（可选，用于代理后端请求）
├── dashboard/             # 用户仪表板
│   ├── layout.tsx         # 仪表板布局
│   └── page.tsx           # 仪表板页面
├── design/                # 设计工作区
│   ├── layout.tsx         # 设计工作区布局
│   └── page.tsx           # 设计创建页面
├── [id]/                  # 具体设计项目（动态路由）
│   ├── layout.tsx         # 项目布局
│   ├── page.tsx           # 项目概览
│   ├── schematic/         # 原理图视图
│   │   ├── layout.tsx     # 原理图布局
│   │   └── page.tsx       # 原理图页面
│   ├── simulation/        # 模拟结果
│   │   ├── layout.tsx     # 模拟结果布局
│   │   └── page.tsx       # 模拟结果页面
│   ├── pcb/               # PCB布局
│   │   ├── layout.tsx     # PCB布局
│   │   └── page.tsx       # PCB页面
│   └── bom/               # BOM清单
│       ├── layout.tsx     # BOM布局
│       └── page.tsx       # BOM页面
├── templates/             # 电路模板库
│   ├── layout.tsx         # 模板库布局
│   ├── page.tsx           # 模板库页面
│   └── [templateId]/      # 具体模板（动态路由）
│       └── page.tsx       # 模板详情页面
├── components/            # 元件库浏览器
│   ├── layout.tsx         # 元件库布局
│   ├── page.tsx           # 元件库页面
│   └── [componentId]/     # 具体元件（动态路由）
│       └── page.tsx       # 元件详情页面
└── auth/                  # 认证页面
    ├── layout.tsx         # 认证布局
    ├── login/             # 登录页面
    │   └── page.tsx
    └── register/          # 注册页面
        └── page.tsx
```

## 路由详细说明

### 1. 根路由
- **路径**: `/`
- **组件**: `app/page.tsx`
- **功能**: 网站首页，展示应用介绍和主要功能入口

### 2. 仪表板路由
- **路径**: `/dashboard`
- **组件**: `app/dashboard/page.tsx`
- **功能**: 用户仪表板，显示用户的设计项目列表、最近活动和统计信息

### 3. 设计工作区路由
- **路径**: `/design`
- **组件**: `app/design/page.tsx`
- **功能**: 新设计创建页面，包含DesignInput组件

### 4. 设计项目路由（动态）
- **路径**: `/:id`
- **组件**: `app/[id]/page.tsx`
- **功能**: 设计项目概览，显示项目基本信息和进度

### 5. 原理图视图路由
- **路径**: `/:id/schematic`
- **组件**: `app/[id]/schematic/page.tsx`
- **功能**: 交互式原理图查看和编辑，包含SchematicViewer组件

### 6. 模拟结果路由
- **路径**: `/:id/simulation`
- **组件**: `app/[id]/simulation/page.tsx`
- **功能**: 显示电路模拟结果，包含SimulationResults组件

### 7. PCB布局路由
- **路径**: `/:id/pcb`
- **组件**: `app/[id]/pcb/page.tsx`
- **功能**: 显示PCB布局和3D预览，包含PCBLayoutViewer组件

### 8. BOM清单路由
- **路径**: `/:id/bom`
- **组件**: `app/[id]/bom/page.tsx`
- **功能**: 显示和编辑BOM，包含BOMEditor组件

### 9. 电路模板库路由
- **路径**: `/templates`
- **组件**: `app/templates/page.tsx`
- **功能**: 展示可用的电路设计模板

### 10. 元件库浏览器路由
- **路径**: `/components`
- **组件**: `app/components/page.tsx`
- **功能**: 浏览和搜索电路元件

### 11. 认证路由
- **路径**: `/auth/login`, `/auth/register`
- **组件**: `app/auth/login/page.tsx`, `app/auth/register/page.tsx`
- **功能**: 用户登录和注册

## 布局组件说明

### 1. 根布局 (`app/layout.tsx`)
- 包含应用的全局导航栏和页脚
- 设置全局样式和主题
- 提供认证状态管理

### 2. 仪表板布局 (`app/dashboard/layout.tsx`)
- 包含仪表板侧边栏
- 显示用户信息和快捷操作

### 3. 设计工作区布局 (`app/design/layout.tsx`)
- 包含设计工具导航
- 提供设计参数配置面板

### 4. 项目布局 (`app/[id]/layout.tsx`)
- 包含项目导航标签页（概览、原理图、模拟、PCB、BOM）
- 显示项目进度和操作按钮

### 5. 功能模块布局
- 原理图、模拟、PCB和BOM页面共享相似的布局结构
- 包含工具栏和视图区域

## 路由守卫

为了保护需要认证的路由，我们将使用Next.js的中间件功能：

```typescript
// middleware.ts
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function middleware(request: NextRequest) {
  // 检查用户是否已认证
  const token = request.cookies.get('auth_token')?.value
  
  // 定义需要认证的路由
  const protectedRoutes = ['/dashboard', '/design', '/[id]', '/templates', '/components']
  
  const isProtectedRoute = protectedRoutes.some(route => 
    request.nextUrl.pathname.startsWith(route)
  )
  
  if (isProtectedRoute && !token) {
    // 未认证用户重定向到登录页面
    return NextResponse.redirect(new URL('/auth/login', request.url))
  }
  
  // 已认证用户访问登录页面重定向到仪表板
  if (request.nextUrl.pathname.startsWith('/auth') && token) {
    return NextResponse.redirect(new URL('/dashboard', request.url))
  }
  
  return NextResponse.next()
}
```

## API路由代理

为了处理与后端API的通信，我们将在前端使用API路由作为代理：

```typescript
// app/api/design/route.ts
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export async function POST(request: NextRequest) {
  const body = await request.json()
  
  // 转发请求到后端API
  const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/design`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      // 传递认证令牌
      'Authorization': request.headers.get('Authorization') || ''
    },
    body: JSON.stringify(body)
  })
  
  const data = await response.json()
  return NextResponse.json(data, { status: response.status })
}
```

这种方式可以帮助我们：
1. 避免CORS问题
2. 隐藏真实的API URL
3. 统一处理认证令牌
4. 在开发环境中简化配置

## 路由转换和动画

为了提升用户体验，我们将使用Next.js的内置路由转换功能：

```typescript
// app/layout.tsx
import { AnimatePresence } from 'framer-motion'
import { usePathname } from 'next/navigation'

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  
  return (
    <html lang="zh-CN">
      <body>
        <AnimatePresence mode="wait">
          <motion.div
            key={pathname}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
          >
            {children}
          </motion.div>
        </AnimatePresence>
      </body>
    </html>
  )
}
```

## 路由总结

这个路由结构设计遵循了Next.js App Router的最佳实践，实现了：

1. **清晰的层次结构**：每个功能模块都有独立的目录
2. **动态路由支持**：使用方括号处理设计ID和模板ID
3. **布局复用**：通过layout.tsx实现布局共享
4. **认证保护**：使用中间件保护需要认证的路由
5. **API代理**：隐藏后端API URL并处理认证
6. **动画效果**：提升用户体验的页面过渡动画

这个结构为我们的电路设计应用提供了坚实的基础，可以支持所有核心功能模块的实现。