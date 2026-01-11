import React from 'react'

export default function Home() {
  return (
    <div style={{ textAlign: 'center', maxWidth: '1200px', margin: '0 auto' }}>
      <h1 style={{ fontSize: '2.5rem', margin: '2rem 0' }}>
        AI 驱动的电路设计系统
      </h1>
      <p style={{ fontSize: '1.2rem', color: '#666', marginBottom: '3rem' }}>
        自动化、智能化的电路设计解决方案
      </p>

      <div style={{ display: 'flex', justifyContent: 'space-around', flexWrap: 'wrap', gap: '2rem', marginBottom: '3rem' }}>
        <div style={{ border: '1px solid #eaeaea', borderRadius: '8px', padding: '2rem', width: '300px', boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)' }}>
          <h3 style={{ marginTop: 0 }}>电路描述解析</h3>
          <p style={{ color: '#666' }}>使用AI技术解析自然语言描述，自动生成电路设计方案</p>
        </div>

        <div style={{ border: '1px solid #eaeaea', borderRadius: '8px', padding: '2rem', width: '300px', boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)' }}>
          <h3 style={{ marginTop: 0 }}>原理图生成</h3>
          <p style={{ color: '#666' }}>自动生成电路原理图，支持实时预览和编辑</p>
        </div>

        <div style={{ border: '1px solid #eaeaea', borderRadius: '8px', padding: '2rem', width: '300px', boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)' }}>
          <h3 style={{ marginTop: 0 }}>PCB布局设计</h3>
          <p style={{ color: '#666' }}>智能生成PCB布局，优化电路性能和可靠性</p>
        </div>
      </div>

      <button style={{ backgroundColor: '#0070f3', color: 'white', border: 'none', padding: '1rem 2rem', fontSize: '1rem', borderRadius: '4px', cursor: 'pointer' }}>
        开始设计
      </button>
    </div>
  )
}