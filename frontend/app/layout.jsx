import React from 'react'

export default function RootLayout({
  children,
}) {
  return (
    <html lang="zh-CN">
      <body>
        <nav style={{ backgroundColor: '#0070f3', padding: '1rem', color: 'white' }}>
          <h1 style={{ margin: 0 }}>AI 电路设计系统</h1>
        </nav>
        <main style={{ padding: '20px' }}>
          {children}
        </main>
      </body>
    </html>
  )
}