"use client";

import React, { useEffect, useRef, useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Alert,
  IconButton,
  Tooltip
} from '@mui/material';
import ZoomInIcon from '@mui/icons-material/ZoomIn';
import ZoomOutIcon from '@mui/icons-material/ZoomOut';
import DownloadIcon from '@mui/icons-material/Download';
import { SVG } from '@svgdotjs/svg.js';
import { downloadSVG } from '../lib/downloadUtils';

export default function SchematicViewer({ svg }) {
  const containerRef = useRef(null);
  const svgInstanceRef = useRef(null);
  const [zoom, setZoom] = useState(1);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!svg || !containerRef.current) return;

    try {
      // Initialize SVG.js
      if (svgInstanceRef.current) {
        svgInstanceRef.current.clear();
      } else {
        svgInstanceRef.current = SVG().addTo(containerRef.current);
        svgInstanceRef.current.size('100%', '100%');
      }

      // Load SVG string
      svgInstanceRef.current.svg(svg);

      // Set initial view
      svgInstanceRef.current.scale(zoom);

      setError(null); // 清除错误状态
    } catch (err) {
      const errorMessage = '无法渲染原理图。可能的原因：SVG格式不正确或数据损坏。请尝试重新生成设计。';
      setError(errorMessage);

      if (process.env.NODE_ENV === 'development') {
        console.error('原理图渲染错误:', err);
      }
    }
  }, [svg, zoom]);

  const handleZoomIn = () => {
    setZoom(prev => Math.min(prev + 0.2, 3));
  };

  const handleZoomOut = () => {
    setZoom(prev => Math.max(prev - 0.2, 0.4));
  };

  const handleDownload = () => {
    if (!svg) {
      setError('没有可下载的原理图数据');
      return;
    }

    const result = downloadSVG(svg, 'schematic.svg');
    if (!result.success) {
      setError('下载失败，请重试');
    }
  };

  // 键盘快捷键 Ctrl+S 下载
  useEffect(() => {
    const handleKeyPress = (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key === 's') {
        event.preventDefault();
        handleDownload();
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [svg]);

  if (!svg) {
    return (
      <Box sx={{ p: 4, textAlign: 'center' }}>
        <Alert severity="info">
          原理图尚未生成，请等待设计生成完成。
        </Alert>
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 4 }}>
        <Alert severity="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      </Box>
    );
  }

  return (
    <Box>
      {/* Toolbar */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6" fontWeight="bold">
          电路原理图
        </Typography>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          <Tooltip title="缩小">
            <span>
              <IconButton onClick={handleZoomOut} disabled={zoom <= 0.4} size="small">
                <ZoomOutIcon />
              </IconButton>
            </span>
          </Tooltip>
          <Typography variant="body2" sx={{ minWidth: 50, textAlign: 'center' }}>
            {Math.round(zoom * 100)}%
          </Typography>
          <Tooltip title="放大">
            <span>
              <IconButton onClick={handleZoomIn} disabled={zoom >= 3} size="small">
                <ZoomInIcon />
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title="下载SVG (Ctrl+S)">
            <IconButton onClick={handleDownload} size="small">
              <DownloadIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* SVG Container */}
      <Paper
        elevation={1}
        sx={{
          p: 2,
          bgcolor: 'white',
          height: { xs: 400, md: 600 },
          overflow: 'auto',
          border: '1px solid #e0e0e0',
          borderRadius: 1
        }}
      >
        <Box
          ref={containerRef}
          sx={{
            width: '100%',
            height: '100%',
            minHeight: { xs: 350, md: 500 },
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}
        />
      </Paper>

      {/* Info */}
      <Box sx={{ mt: 2 }}>
        <Typography variant="body2" color="text.secondary">
          💡 提示：使用缩放按钮调整视图大小，点击下载按钮保存为SVG文件（支持Ctrl+S快捷键）。
        </Typography>
      </Box>
    </Box>
  );
}
