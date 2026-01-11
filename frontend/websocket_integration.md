# WebSocket集成策略（SSR兼容）

## 1. 概述

WebSocket集成是电路设计系统的关键部分，用于实现实时设计进度更新、多人协作和状态同步。本策略确保WebSocket在Next.js的SSR环境中正确工作，并与现有的状态管理方案无缝集成。

## 2. WebSocket服务设计

### 2.1 Socket.io客户端服务

```typescript
// src/services/websocketService.ts
import { io, Socket } from 'socket.io-client'
import { useAppStore } from '@/store/useAppStore'

class WebSocketService {
  private socket: Socket | null = null
  private listeners: Map<string, Set<(data: any) => void>> = new Map()
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 1000

  constructor() {
    // 初始化时不自动连接，确保在客户端使用
  }

  // 建立连接
  connect(): Promise<Socket> {
    return new Promise((resolve, reject) => {
      if (this.socket?.connected) {
        resolve(this.socket)
        return
      }

      try {
        // 从环境变量获取WebSocket URL
        const wsUrl = process.env.NEXT_PUBLIC_WEBSOCKET_URL
        
        if (!wsUrl) {
          throw new Error('WebSocket URL not configured')
        }

        // 获取认证令牌
        const token = document.cookie.split('; ')
          .find(row => row.startsWith('auth_token='))?.split('=')[1]

        // 创建Socket.io实例
        this.socket = io(wsUrl, {
          transports: ['websocket'],
          auth: {
            token
          },
          reconnectionAttempts: this.maxReconnectAttempts,
          reconnectionDelay: this.reconnectDelay,
          timeout: 5000
        })

        // 连接成功事件
        this.socket.on('connect', () => {
          console.log('WebSocket connected')
          this.reconnectAttempts = 0
          resolve(this.socket!)
        })

        // 连接错误事件
        this.socket.on('connect_error', (error) => {
          console.error('WebSocket connection error:', error)
          reject(error)
        })

        // 断开连接事件
        this.socket.on('disconnect', (reason) => {
          console.log('WebSocket disconnected:', reason)
          if (reason === 'io server disconnect') {
            // 服务器主动断开，不自动重连
            this.socket?.connect()
          }
        })

        // 重新连接尝试事件
        this.socket.on('reconnect_attempt', (attempt) => {
          console.log(`WebSocket reconnect attempt ${attempt}`)
          this.reconnectAttempts = attempt
        })

        // 重新连接成功事件
        this.socket.on('reconnect', (attempt) => {
          console.log(`WebSocket reconnected after ${attempt} attempts`)
          this.reconnectAttempts = 0
        })

        // 重新连接失败事件
        this.socket.on('reconnect_error', (error) => {
          console.error('WebSocket reconnection error:', error)
        })

        // 重新连接放弃事件
        this.socket.on('reconnect_failed', () => {
          console.error('WebSocket reconnection failed after all attempts')
        })

      } catch (error) {
        console.error('Failed to initialize WebSocket:', error)
        reject(error)
      }
    })
  }

  // 断开连接
  disconnect() {
    if (this.socket?.connected) {
      this.socket.disconnect()
      this.socket = null
      this.listeners.clear()
      console.log('WebSocket disconnected')
    }
  }

  // 订阅事件
  subscribe(event: string, callback: (data: any) => void): () => void {
    // 如果没有监听器集合，创建一个
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set())
    }

    // 添加监听器
    const eventListeners = this.listeners.get(event)!
    eventListeners.add(callback)

    // 如果socket已连接，添加事件监听器
    if (this.socket?.connected) {
      this.socket.on(event, callback)
    }

    // 返回取消订阅函数
    return () => {
      eventListeners.delete(callback)
      if (this.socket?.connected) {
        this.socket.off(event, callback)
      }
      // 如果没有监听器了，删除该事件
      if (eventListeners.size === 0) {
        this.listeners.delete(event)
      }
    }
  }

  // 发送事件
  emit(event: string, data: any): Promise<void> {
    return new Promise((resolve, reject) => {
      if (!this.socket?.connected) {
        reject(new Error('WebSocket not connected'))
        return
      }

      this.socket.emit(event, data, (ack: any) => {
        if (ack?.error) {
          reject(new Error(ack.error))
        } else {
          resolve()
        }
      })
    })
  }

  // 获取连接状态
  isConnected(): boolean {
    return this.socket?.connected || false
  }

  // 获取连接实例
  getSocket(): Socket | null {
    return this.socket
  }
}

// 导出单例实例
export const websocketService = new WebSocketService()
```

### 2.2 React Hook封装

```typescript
// src/hooks/useWebSocket.ts
'use client'

import { useEffect, useState } from 'react'
import { websocketService } from '@/services/websocketService'

export const useWebSocket = () => {
  const [isConnected, setIsConnected] = useState(false)
  const [connectionError, setConnectionError] = useState<string | null>(null)

  useEffect(() => {
    // 建立WebSocket连接
    const connectWebSocket = async () => {
      try {
        await websocketService.connect()
        setIsConnected(true)
        setConnectionError(null)
      } catch (error) {
        setConnectionError((error as Error).message)
        setIsConnected(false)
      }
    }

    connectWebSocket()

    // 监听连接状态变化
    const handleConnect = () => setIsConnected(true)
    const handleDisconnect = () => setIsConnected(false)
    const handleError = (error: Error) => setConnectionError(error.message)

    // 使用WebSocket服务的订阅功能
    const unsubscribeConnect = websocketService.subscribe('connect', handleConnect)
    const unsubscribeDisconnect = websocketService.subscribe('disconnect', handleDisconnect)
    const unsubscribeError = websocketService.subscribe('connect_error', handleError)

    // 组件卸载时断开连接
    return () => {
      unsubscribeConnect()
      unsubscribeDisconnect()
      unsubscribeError()
      // 注意：这里可以选择是否断开连接
      // 如果是全局WebSocket，可以保持连接
      // websocketService.disconnect()
    }
  }, [])

  return {
    isConnected,
    connectionError,
    send: websocketService.emit.bind(websocketService),
    subscribe: websocketService.subscribe.bind(websocketService),
    disconnect: websocketService.disconnect.bind(websocketService)
  }
}
```

## 3. SSR兼容实现

### 3.1 客户端组件中的WebSocket使用

```typescript
// src/components/DesignProgress/DesignProgress.tsx
'use client'

import { useEffect } from 'react'
import { useAppStore } from '@/store/useAppStore'
import { useWebSocket } from '@/hooks/useWebSocket'
import { LinearProgress, Paper, Typography, Box, Chip } from '@mui/material'

const DesignProgress = () => {
  const { designProgress, setDesignProgress } = useAppStore()
  const { subscribe } = useWebSocket()

  useEffect(() => {
    // 订阅设计进度更新事件
    const unsubscribe = subscribe('design_progress', (data) => {
      setDesignProgress({
        stage: data.stage,
        percentage: data.percentage,
        message: data.message
      })
    })

    // 组件卸载时取消订阅
    return () => unsubscribe()
  }, [subscribe, setDesignProgress])

  // 组件其余部分...
}

export default DesignProgress
```

### 3.2 与React Query集成

```typescript
// src/services/designService.ts
import { useQueryClient } from '@tanstack/react-query'
import { websocketService } from '@/services/websocketService'

// 初始化WebSocket与React Query的集成
export const initWebSocketQueryIntegration = () => {
  const queryClient = useQueryClient()

  // 订阅设计更新事件
  websocketService.subscribe('design_updated', (data) => {
    // 更新设计数据
    queryClient.setQueryData(['design', data.designId], data.design)
    // 使设计列表失效，重新获取
    queryClient.invalidateQueries({ queryKey: ['designs'] })
  })

  // 订阅设计删除事件
  websocketService.subscribe('design_deleted', (data) => {
    // 从缓存中删除设计
    queryClient.removeQueries({ queryKey: ['design', data.designId] })
    // 使设计列表失效，重新获取
    queryClient.invalidateQueries({ queryKey: ['designs'] })
  })
}
```

```typescript
// src/app/layout.tsx
'use client'

import { useEffect } from 'react'
import { initWebSocketQueryIntegration } from '@/services/designService'

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // 初始化WebSocket与React Query的集成
  useEffect(() => {
    initWebSocketQueryIntegration()
  }, [])

  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  )
}
```

## 4. 认证与安全

### 4.1 WebSocket认证

```typescript
// src/services/websocketService.ts
// 在connect方法中添加认证信息

connect(): Promise<Socket> {
  return new Promise((resolve, reject) => {
    // ...

    // 获取认证令牌
    const token = document.cookie.split('; ')
      .find(row => row.startsWith('auth_token='))?.split('=')[1]

    // 创建Socket.io实例
    this.socket = io(wsUrl, {
      transports: ['websocket'],
      auth: {
        token
      },
      // ...
    })

    // ...
  })
}
```

### 4.2 消息验证

```typescript
// src/services/websocketService.ts
// 扩展WebSocketService，添加消息验证

class WebSocketService {
  // ...

  // 发送事件（带验证）
  emit(event: string, data: any): Promise<void> {
    return new Promise((resolve, reject) => {
      // ...

      // 验证数据格式
      if (!this.validateEventData(event, data)) {
        reject(new Error('Invalid event data'))
        return
      }

      this.socket?.emit(event, data, (ack: any) => {
        // ...
      })
    })
  }

  // 验证事件数据格式
  private validateEventData(event: string, data: any): boolean {
    const validators: Record<string, (data: any) => boolean> = {
      'design_progress': (d) => d.designId && d.stage && d.percentage >= 0 && d.percentage <= 100,
      'design_updated': (d) => d.designId && d.design,
      'design_deleted': (d) => d.designId
    }

    const validator = validators[event]
    return validator ? validator(data) : true
  }
}
```

## 5. 断开重连策略

```typescript
// src/services/websocketService.ts
// 已经包含在WebSocketService类中

class WebSocketService {
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 1000

  constructor() {
    // ...
  }

  connect(): Promise<Socket> {
    return new Promise((resolve, reject) => {
      // ...

      // 创建Socket.io实例
      this.socket = io(wsUrl, {
        // ...
        reconnectionAttempts: this.maxReconnectAttempts,
        reconnectionDelay: this.reconnectDelay,
        // ...
      })

      // 重新连接尝试事件
      this.socket.on('reconnect_attempt', (attempt) => {
        console.log(`WebSocket reconnect attempt ${attempt}`)
        this.reconnectAttempts = attempt
      })

      // 重新连接成功事件
      this.socket.on('reconnect', (attempt) => {
        console.log(`WebSocket reconnected after ${attempt} attempts`)
        this.reconnectAttempts = 0
      })

      // 重新连接失败事件
      this.socket.on('reconnect_error', (error) => {
        console.error('WebSocket reconnection error:', error)
      })

      // 重新连接放弃事件
      this.socket.on('reconnect_failed', () => {
        console.error('WebSocket reconnection failed after all attempts')
      })

      // ...
    })
  }
}
```

## 6. 性能优化

### 6.1 批量更新

```typescript
// src/services/websocketService.ts
// 添加批量更新功能

class WebSocketService {
  // ...
  private batchUpdates: Map<string, any> = new Map()
  private batchTimer: NodeJS.Timeout | null = null
  private batchInterval = 100 // 批量更新间隔（毫秒）

  // 批量更新事件
  emitBatch(event: string, data: any): void {
    // 将更新添加到批处理队列
    this.batchUpdates.set(event, data)

    // 如果没有定时器，创建一个
    if (!this.batchTimer) {
      this.batchTimer = setTimeout(() => {
        // 发送所有批量更新
        this.batchUpdates.forEach((data, event) => {
          this.emit(event, data).catch(console.error)
        })

        // 清空批处理队列
        this.batchUpdates.clear()
        this.batchTimer = null
      }, this.batchInterval)
    }
  }
}
```

### 6.2 事件节流

```typescript
// src/hooks/useWebSocket.ts
// 添加节流功能

import { throttle } from 'lodash'

export const useWebSocket = () => {
  // ...

  // 节流发送方法
  const sendThrottled = throttle(websocketService.emit.bind(websocketService), 100)

  return {
    // ...
    send: sendThrottled
  }
}
```

## 7. 测试策略

### 7.1 单元测试

```typescript
// src/services/__tests__/websocketService.test.ts
import { WebSocketService } from '../websocketService'

describe('WebSocketService', () => {
  let wsService: WebSocketService

  beforeEach(() => {
    wsService = new WebSocketService()
    // 模拟Socket.io客户端
    jest.mock('socket.io-client', () => ({
      io: jest.fn(() => ({
        connected: false,
        connect: jest.fn(),
        disconnect: jest.fn(),
        on: jest.fn(),
        off: jest.fn(),
        emit: jest.fn((event, data, callback) => callback?.())
      }))
    }))
  })

  afterEach(() => {
    jest.clearAllMocks()
  })

  test('should connect successfully', async () => {
    // 测试连接逻辑
  })

  test('should subscribe to events', () => {
    // 测试订阅逻辑
  })

  test('should emit events', async () => {
    // 测试发送事件逻辑
  })

  // 更多测试...
})
```

### 7.2 集成测试

```typescript
// src/components/__tests__/DesignProgress.test.tsx
import { render, screen } from '@testing-library/react'
import DesignProgress from '../DesignProgress/DesignProgress'
import { useAppStore } from '@/store/useAppStore'
import { useWebSocket } from '@/hooks/useWebSocket'

jest.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: jest.fn(() => ({
    subscribe: jest.fn(() => jest.fn())
  }))
}))

describe('DesignProgress', () => {
  beforeEach(() => {
    useAppStore.setState({
      designProgress: {
        stage: 'parsing',
        percentage: 0,
        message: 'Initializing'
      }
    })
  })

  test('should render progress component', () => {
    render(<DesignProgress />)
    expect(screen.getByText('设计进度')).toBeInTheDocument()
  })

  // 更多测试...
})
```

## 8. 总结

本WebSocket集成策略确保了：

1. **SSR兼容性**：只在客户端建立WebSocket连接，避免服务器端错误
2. **可靠连接**：实现了连接、断开、重连和错误处理机制
3. **状态同步**：与Zustand和React Query集成，确保UI与实时数据同步
4. **性能优化**：支持批量更新和事件节流，减少网络流量
5. **安全认证**：正确传递认证令牌，确保连接安全
6. **可测试性**：提供了单元测试和集成测试方案

该策略为电路设计系统的实时功能提供了坚实的基础，提升了用户体验和系统响应性。