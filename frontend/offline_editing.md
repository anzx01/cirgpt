# 离线编辑和自动保存机制设计

## 1. 概述

离线编辑和自动保存机制是电路设计系统的重要特性，确保用户在没有网络连接时仍能继续工作，并自动保存工作进度以防止数据丢失。本设计方案将集成到现有的Next.js应用架构中，与状态管理和WebSocket系统无缝协作。

## 2. 技术选择

| 技术 | 用途 | 优势 | 限制 |
|------|------|------|------|
| IndexedDB | 主要数据存储 | 大容量、结构化查询、事务支持 | API复杂 |
| localStorage | 备份存储 | 简单易用、浏览器支持广泛 | 容量有限（5-10MB） |
| Service Worker | 网络拦截和离线支持 | 真正的离线体验、请求缓存 | 实现复杂度高 |
| PouchDB | IndexedDB封装 | 简化IndexedDB使用、支持同步 | 额外依赖 |
| Y.js | 冲突解决 | 实时协作、自动冲突解决 | 学习曲线较陡 |

**最终选择**：IndexedDB + Service Worker + 自定义冲突解决

## 3. 数据模型设计

### 3.1 IndexedDB存储结构

```javascript
// src/services/indexedDBService.ts
import { CircuitDesign } from '@/store/useAppStore'

interface DBDesign extends CircuitDesign {
  isLocal: boolean           // 是否为本地设计
  lastModified: number       // 最后修改时间戳
  syncStatus: 'synced' | 'syncing' | 'conflict' | 'unsynced'  // 同步状态
  version: number            // 版本号（用于冲突检测）
}

interface DBSimulationResult {
  id: string                 // 模拟结果ID
  designId: string           // 关联的设计ID
  resultData: any            // 模拟结果数据
  createdAt: number          // 创建时间
}

interface DBComponent {
  id: string                 // 元件ID
  designId: string           // 关联的设计ID
  // 元件详细信息（与CircuitComponent相同）
}

interface DBConnection {
  id: string                 // 连接ID
  designId: string           // 关联的设计ID
  // 连接详细信息（与CircuitConnection相同）
}
```

### 3.2 数据库创建和版本管理

```typescript
// src/services/indexedDBService.ts
class IndexedDBService {
  private db: IDBDatabase | null = null
  private dbName = 'circuitGPT'
  private dbVersion = 1

  async init(): Promise<IDBDatabase> {
    return new Promise((resolve, reject) => {
      if (this.db) {
        resolve(this.db)
        return
      }

      const request = indexedDB.open(this.dbName, this.dbVersion)

      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result

        // 创建设计存储
        const designsStore = db.createObjectStore('designs', {
          keyPath: 'id',
          autoIncrement: false
        })
        designsStore.createIndex('lastModified', 'lastModified', { unique: false })
        designsStore.createIndex('syncStatus', 'syncStatus', { unique: false })

        // 创建模拟结果存储
        const simulationsStore = db.createObjectStore('simulations', {
          keyPath: 'id',
          autoIncrement: true
        })
        simulationsStore.createIndex('designId', 'designId', { unique: false })

        // 创建元件存储
        const componentsStore = db.createObjectStore('components', {
          keyPath: 'id',
          autoIncrement: false
        })
        componentsStore.createIndex('designId', 'designId', { unique: false })

        // 创建连接存储
        const connectionsStore = db.createObjectStore('connections', {
          keyPath: 'id',
          autoIncrement: false
        })
        connectionsStore.createIndex('designId', 'designId', { unique: false })
      }

      request.onsuccess = (event) => {
        this.db = (event.target as IDBOpenDBRequest).result
        resolve(this.db)
      }

      request.onerror = (event) => {
        reject((event.target as IDBOpenDBRequest).error)
      }
    })
  }

  // 其他数据库操作方法...
}

export const indexedDBService = new IndexedDBService()
```

## 4. 自动保存机制

### 4.1 保存策略

| 策略 | 触发条件 | 频率 | 优势 |
|------|----------|------|------|
| 定时保存 | 时间间隔 | 15秒 | 简单可靠 |
| 变更保存 | 数据变更 | 实时 | 确保最新变更 |
| 离开保存 | 页面切换或关闭 | 一次 | 防止意外关闭 |
| 手动保存 | 用户操作 | 按需 | 用户控制 |

**最终策略**：定时保存（15秒）+ 变更保存（重要操作）+ 离开保存

### 4.2 自动保存实现

```typescript
// src/services/autosaveService.ts
import { useAppStore, CircuitDesign } from '@/store/useAppStore'
import { indexedDBService } from './indexedDBService'

class AutosaveService {
  private saveInterval: NodeJS.Timeout | null = null
  private saveIntervalTime = 15000 // 15秒
  private pendingChanges = false
  private isSaving = false

  constructor() {
    // 初始化时不自动保存，确保在客户端使用
  }

  // 开始自动保存
  start(designId: string): void {
    // 清除现有定时器
    this.stop()

    // 设置定时保存
    this.saveInterval = setInterval(() => {
      this.save(designId)
    }, this.saveIntervalTime)

    // 监听页面离开事件
    window.addEventListener('beforeunload', () => this.save(designId))
  }

  // 停止自动保存
  stop(): void {
    if (this.saveInterval) {
      clearInterval(this.saveInterval)
      this.saveInterval = null
    }
    window.removeEventListener('beforeunload', this.save.bind(this))
  }

  // 标记有变更需要保存
  markChanged(): void {
    this.pendingChanges = true
  }

  // 手动保存
  async save(designId: string): Promise<void> {
    if (this.isSaving) return
    
    try {
      this.isSaving = true
      const store = useAppStore.getState()
      const design = store.currentDesign

      if (!design || design.id !== designId) return

      // 保存到IndexedDB
      await indexedDBService.saveDesign({
        ...design,
        lastModified: Date.now(),
        syncStatus: 'unsynced',
        version: (design as any).version ? (design as any).version + 1 : 1
      })

      // 保存到localStorage作为备份
      localStorage.setItem(`design_${designId}`, JSON.stringify(design))

      this.pendingChanges = false
      console.log('Design autosaved successfully')
    } catch (error) {
      console.error('Autosave failed:', error)
    } finally {
      this.isSaving = false
    }
  }
}

export const autosaveService = new AutosaveService()
```

### 4.3 与状态管理集成

```typescript
// src/store/useAppStore.ts
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { autosaveService } from '@/services/autosaveService'

// ... existing store definition ...

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      // ... existing state and actions ...

      // 更新设计时触发自动保存
      updateDesign: (updatedDesign) => {
        set((state) => {
          const newDesign = {
            ...(state.currentDesign as CircuitDesign),
            ...updatedDesign,
            updatedAt: new Date()
          }
          
          // 标记有变更需要保存
          autosaveService.markChanged()
          
          return {
            designs: state.designs.map((design) =>
              design.id === updatedDesign.id ? newDesign : design
            ),
            currentDesign: state.currentDesign?.id === updatedDesign.id ? newDesign : state.currentDesign
          }
        })
      },

      // 保存组件位置时触发自动保存
      updateComponentPosition: (componentId, position) => {
        set((state) => {
          if (!state.currentDesign) return state

          const newComponents = state.currentDesign.components.map((component) =>
            component.id === componentId
              ? { ...component, position }
              : component
          )

          const newDesign = {
            ...state.currentDesign,
            components: newComponents,
            updatedAt: new Date()
          }

          // 标记有变更需要保存
          autosaveService.markChanged()

          return {
            currentDesign: newDesign,
            designs: state.designs.map((design) =>
              design.id === state.currentDesign?.id ? newDesign : design
            )
          }
        })
      }
    }),
    // ... existing persist options ...
  )
)
```

## 5. 离线同步机制

### 5.1 网络状态监听

```typescript
// src/services/networkService.ts
class NetworkService {
  private isOnline = navigator.onLine
  private listeners: Set<(isOnline: boolean) => void> = new Set()

  constructor() {
    // 监听网络状态变化
    window.addEventListener('online', () => this.updateOnlineStatus(true))
    window.addEventListener('offline', () => this.updateOnlineStatus(false))
  }

  private updateOnlineStatus(isOnline: boolean) {
    this.isOnline = isOnline
    this.listeners.forEach(listener => listener(isOnline))
  }

  isNetworkOnline(): boolean {
    return this.isOnline
  }

  onNetworkChange(callback: (isOnline: boolean) => void): () => void {
    this.listeners.add(callback)
    return () => this.listeners.delete(callback)
  }
}

export const networkService = new NetworkService()
```

### 5.2 离线同步实现

```typescript
// src/services/syncService.ts
import { indexedDBService } from './indexedDBService'
import { useDesigns, useUpdateDesign } from '@/services/designService'
import { networkService } from './networkService'

class SyncService {
  private syncInterval: NodeJS.Timeout | null = null
  private syncIntervalTime = 60000 // 1分钟

  constructor() {
    // 监听网络状态变化
    networkService.onNetworkChange((isOnline) => {
      if (isOnline) {
        this.start()
        this.syncAll()
      } else {
        this.stop()
      }
    })
  }

  start(): void {
    this.stop()
    this.syncInterval = setInterval(() => {
      this.syncAll()
    }, this.syncIntervalTime)
  }

  stop(): void {
    if (this.syncInterval) {
      clearInterval(this.syncInterval)
      this.syncInterval = null
    }
  }

  // 同步所有未同步的设计
  async syncAll(): Promise<void> {
    if (!networkService.isNetworkOnline()) return

    try {
      const unsyncedDesigns = await indexedDBService.getUnsyncedDesigns()
      
      for (const design of unsyncedDesigns) {
        await this.syncDesign(design)
      }
    } catch (error) {
      console.error('Sync all failed:', error)
    }
  }

  // 同步单个设计
  async syncDesign(design: any): Promise<void> {
    try {
      // 更新设计同步状态
      await indexedDBService.updateSyncStatus(design.id, 'syncing')

      const updateDesign = useUpdateDesign.getState()
      
      // 调用API更新设计
      await updateDesign.mutateAsync({
        id: design.id,
        data: design
      })

      // 更新设计同步状态为已同步
      await indexedDBService.updateSyncStatus(design.id, 'synced')
      
      console.log(`Design ${design.id} synced successfully`)
    } catch (error) {
      console.error(`Sync design ${design.id} failed:`, error)
      
      // 检查是否为冲突错误
      if (this.isConflictError(error)) {
        await indexedDBService.updateSyncStatus(design.id, 'conflict')
      } else {
        await indexedDBService.updateSyncStatus(design.id, 'unsynced')
      }
    }
  }

  // 检测是否为冲突错误
  private isConflictError(error: any): boolean {
    // 根据API返回的错误类型判断是否为冲突
    return error?.response?.status === 409 || 
           error?.message?.includes('conflict') ||
           error?.message?.includes('version mismatch')
  }

  // 解决冲突
  async resolveConflict(designId: string, serverDesign: any): Promise<void> {
    try {
      const localDesign = await indexedDBService.getDesign(designId)
      if (!localDesign) return

      // 简单的冲突解决策略：保留本地修改，标记为新设计
      const newDesign = {
        ...localDesign,
        id: `local_${Date.now()}`,
        name: `${localDesign.name} (本地副本)`,
        isLocal: true,
        syncStatus: 'unsynced',
        version: 1
      }

      // 保存解决后的设计
      await indexedDBService.saveDesign(newDesign)
      
      console.log(`Conflict resolved for design ${designId}`)
    } catch (error) {
      console.error(`Resolve conflict failed for design ${designId}:`, error)
    }
  }
}

export const syncService = new SyncService()
```

## 6. Service Worker实现

### 6.1 Service Worker配置

```javascript
// public/service-worker.js
const CACHE_NAME = 'circuit-gpt-v1'
const ASSETS_TO_CACHE = [
  '/',
  '/index.html',
  '/manifest.json',
  // 其他静态资源
]

// 安装Service Worker
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(ASSETS_TO_CACHE))
      .then(() => self.skipWaiting())
  )
})

// 激活Service Worker
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName)
          }
        })
      )
    }).then(() => self.clients.claim())
  )
})

// 拦截网络请求
self.addEventListener('fetch', (event) => {
  // API请求策略：网络优先，失败则返回缓存
  if (event.request.url.startsWith('http://') || event.request.url.startsWith('https://')) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          // 如果响应成功，缓存一份
          const responseToCache = response.clone()
          caches.open(CACHE_NAME)
            .then((cache) => {
              cache.put(event.request, responseToCache)
            })
          return response
        })
        .catch(() => {
          // 网络请求失败，返回缓存
          return caches.match(event.request)
        })
    )
  }
})
```

### 6.2 Next.js集成

```javascript
// src/pages/_app.tsx
'use client'

import { useEffect } from 'react'

export default function App({ Component, pageProps }: AppProps) {
  // 注册Service Worker
  useEffect(() => {
    if ('serviceWorker' in navigator) {
      window.addEventListener('load', () => {
        navigator.serviceWorker.register('/service-worker.js')
          .then((registration) => {
            console.log('Service Worker registered:', registration)
          })
          .catch((error) => {
            console.error('Service Worker registration failed:', error)
          })
      })
    }
  }, [])

  return <Component {...pageProps} />
}
```

## 7. 用户界面集成

### 7.1 离线状态指示器

```typescript
// src/components/OfflineIndicator/OfflineIndicator.tsx
'use client'

import { useEffect, useState } from 'react'
import { networkService } from '@/services/networkService'
import { Paper, Typography, Chip, Box } from '@mui/material'
import { CloudOff, CloudUpload, CloudUploadOutlined } from '@mui/icons-material'

const OfflineIndicator = () => {
  const [isOnline, setIsOnline] = useState(networkService.isNetworkOnline())
  const [syncStatus, setSyncStatus] = useState<'synced' | 'syncing' | 'unsynced' | 'conflict'>('synced')

  useEffect(() => {
    // 监听网络状态变化
    const unsubscribe = networkService.onNetworkChange((online) => {
      setIsOnline(online)
    })

    return () => unsubscribe()
  }, [])

  const getIndicatorContent = () => {
    if (!isOnline) {
      return (
        <Chip
          icon={<CloudOff />}
          label="离线模式"
          color="warning"
          size="small"
        />
      )
    }

    switch (syncStatus) {
      case 'syncing':
        return (
          <Chip
            icon={<CloudUploadOutlined />}
            label="正在同步..."
            color="info"
            size="small"
          />
        )
      case 'unsynced':
        return (
          <Chip
            icon={<CloudUpload />}
            label="有未同步更改"
            color="warning"
            size="small"
          />
        )
      case 'conflict':
        return (
          <Chip
            icon={<CloudUpload />}
            label="同步冲突"
            color="error"
            size="small"
          />
        )
      default:
        return null
    }
  }

  if (syncStatus === 'synced' && isOnline) return null

  return (
    <Box sx={{ position: 'fixed', bottom: 16, right: 16, zIndex: 1000 }}>
      {getIndicatorContent()}
    </Box>
  )
}

export default OfflineIndicator
```

### 7.2 冲突解决对话框

```typescript
// src/components/ConflictDialog/ConflictDialog.tsx
'use client'

import { useState } from 'react'
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, Typography, Box } from '@mui/material'
import { syncService } from '@/services/syncService'

interface ConflictDialogProps {
  open: boolean
  onClose: () => void
  designId: string
  serverDesign?: any
}

const ConflictDialog = ({ open, onClose, designId, serverDesign }: ConflictDialogProps) => {
  const [isResolving, setIsResolving] = useState(false)

  const handleResolve = async () => {
    if (!serverDesign) return
    
    try {
      setIsResolving(true)
      await syncService.resolveConflict(designId, serverDesign)
      onClose()
    } catch (error) {
      console.error('Resolve conflict failed:', error)
    } finally {
      setIsResolving(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>同步冲突</DialogTitle>
      <DialogContent>
        <Typography variant="body1" gutterBottom>
          设计 "{serverDesign?.name}" 在服务器上已被修改，与您的本地版本存在冲突。
        </Typography>
        <Box sx={{ mt: 2 }}>
          <Typography variant="subtitle1">本地版本:</Typography>
          <Typography variant="body2" color="text.secondary">
            最后修改: {new Date().toLocaleString()}
          </Typography>
          <Typography variant="subtitle1" sx={{ mt: 2 }}>
            服务器版本:
          </Typography>
          <Typography variant="body2" color="text.secondary">
            最后修改: {new Date(serverDesign?.updatedAt).toLocaleString()}
          </Typography>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={isResolving}>
          取消
        </Button>
        <Button onClick={handleResolve} color="primary" disabled={isResolving}>
          {isResolving ? '解决中...' : '创建本地副本'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}

export default ConflictDialog
```

## 8. 性能优化

### 8.1 存储优化

1. **增量保存**：只保存变更的部分，而非整个设计
2. **压缩存储**：使用LZ字符串或其他压缩算法减少存储大小
3. **过期清理**：定期清理长时间未使用的本地设计

### 8.2 同步优化

1. **批量同步**：合并多个小的同步请求
2. **优先级同步**：优先同步重要的设计变更
3. **网络自适应**：根据网络状况调整同步频率

### 8.3 内存优化

1. **虚拟滚动**：对于大型设计，使用虚拟滚动技术
2. **按需加载**：只加载当前视图需要的数据
3. **内存缓存**：减少重复的数据库查询

## 9. 测试策略

### 9.1 单元测试

```typescript
// src/services/__tests__/autosaveService.test.ts
import { AutosaveService } from '../autosaveService'

describe('AutosaveService', () => {
  let autosaveService: AutosaveService

  beforeEach(() => {
    autosaveService = new AutosaveService()
  })

  test('should start and stop autosave', () => {
    jest.useFakeTimers()
    
    const designId = 'test-design'
    autosaveService.start(designId)
    
    // 验证定时器已设置
    expect(setInterval).toHaveBeenCalled()
    
    autosaveService.stop()
    
    // 验证定时器已清除
    expect(clearInterval).toHaveBeenCalled()
    
    jest.useRealTimers()
  })

  // 更多测试...
})
```

### 9.2 集成测试

```typescript
// src/components/__tests__/OfflineIndicator.test.tsx
import { render, screen } from '@testing-library/react'
import OfflineIndicator from '../OfflineIndicator/OfflineIndicator'
import { networkService } from '@/services/networkService'

describe('OfflineIndicator', () => {
  test('should show offline indicator when offline', () => {
    // 模拟离线状态
    Object.defineProperty(navigator, 'onLine', {
      value: false,
      writable: true
    })
    
    render(<OfflineIndicator />)
    expect(screen.getByText('离线模式')).toBeInTheDocument()
  })

  test('should not show when online and synced', () => {
    // 模拟在线状态
    Object.defineProperty(navigator, 'onLine', {
      value: true,
      writable: true
    })
    
    const { container } = render(<OfflineIndicator />)
    expect(container.firstChild).toBeNull()
  })

  // 更多测试...
})
```

### 9.3 离线测试

1. **浏览器开发者工具**：使用Chrome开发者工具模拟离线状态
2. **Cypress测试**：使用Cypress进行端到端的离线测试
3. **真实环境测试**：在实际的离线环境中测试功能

## 10. 总结

本离线编辑和自动保存机制设计实现了以下功能：

1. **可靠的本地存储**：使用IndexedDB存储设计数据，确保大容量和结构化查询
2. **灵活的自动保存**：结合定时保存、变更保存和离开保存策略
3. **智能的离线同步**：网络恢复时自动同步，处理冲突
4. **真正的离线体验**：使用Service Worker实现完整的离线支持
5. **用户友好的界面**：提供离线状态指示和冲突解决界面
6. **性能优化**：通过增量保存、压缩存储和批量同步优化性能

该设计与现有的Next.js应用架构无缝集成，确保用户在各种网络条件下都能顺畅地使用电路设计系统。