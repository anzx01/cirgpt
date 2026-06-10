"use client";

import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Alert,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Grid
} from '@mui/material';
import ZoomInIcon from '@mui/icons-material/ZoomIn';
import ZoomOutIcon from '@mui/icons-material/ZoomOut';
import FullscreenIcon from '@mui/icons-material/Fullscreen';
import DownloadIcon from '@mui/icons-material/Download';
import { downloadImage } from '../lib/downloadUtils';

export default function PcbViewer({ layout, image }) {
  const [zoom, setZoom] = useState(1);
  const [fullscreen, setFullscreen] = useState(false);
  const [imageError, setImageError] = useState(false);

  // Debug: log the image prop (仅开发环境)
  useEffect(() => {
    if (image && process.env.NODE_ENV === 'development') {
      console.log('PCB Image data type:', typeof image);
      console.log('PCB Image length:', image?.length);
      console.log('PCB Image prefix:', image?.substring(0, 50));
    }
  }, [image]);

  if (!layout && !image) {
    return (
      <Box sx={{ p: 4, textAlign: 'center' }}>
        <Alert severity="info">
          PCB布局尚未生成，请等待设计生成完成。
        </Alert>
      </Box>
    );
  }

  const handleZoomIn = () => {
    setZoom(prev => Math.min(prev + 0.2, 3));
  };

  const handleZoomOut = () => {
    setZoom(prev => Math.max(prev - 0.2, 0.4));
  };

  const handleDownload = () => {
    if (!image) {
      setImageError(true);
      return;
    }

    const result = downloadImage(image, 'pcb-layout');
    if (!result.success) {
      alert('下载失败，请重试');
      if (process.env.NODE_ENV === 'development') {
        console.error('下载错误:', result.error);
      }
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
  }, [image]);

  // Handle different image formats (SVG, base64 PNG, data URLs)
  const getImageSrc = (imgData) => {
    if (!imgData) return '';

    // If already a data URL, use as-is
    if (imgData.startsWith('data:image')) {
      return imgData;
    }

    // Check if it's an SVG string
    if (imgData.trim().startsWith('<svg')) {
      // SVG needs to be URI-encoded and use svg+xml MIME type
      return `data:image/svg+xml,${encodeURIComponent(imgData)}`;
    }

    // Otherwise, assume it's base64 PNG
    return `data:image/png;base64,${imgData}`;
  };

  const pcbImage = (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        overflow: 'auto',
        height: fullscreen ? '80vh' : { xs: 400, md: 600 },
        bgcolor: '#2e7d32', // PCB green color
        borderRadius: 1
      }}
    >
      {image ? (
        <>
          <img
            src={getImageSrc(image)}
            alt="PCB Layout"
            onError={(e) => {
              if (process.env.NODE_ENV === 'development') {
                console.error('图片加载失败');
                console.error('图片源:', getImageSrc(image)?.substring(0, 100));
              }
              setImageError(true);
              e.target.style.display = 'none';
            }}
            style={{
              maxWidth: '100%',
              maxHeight: fullscreen ? '100%' : '580px',
              transform: `scale(${zoom})`,
              transition: 'transform 0.3s ease',
              display: imageError ? 'none' : 'block'
            }}
          />
          {imageError && (
            <Box sx={{ color: 'white', p: 4, textAlign: 'center' }}>
              <Alert severity="error" sx={{ mb: 2 }}>
                无法加载PCB布局图片。可能的原因：图片格式不支持或数据损坏。
              </Alert>
              <Typography variant="body2" sx={{ color: 'white' }}>
                请尝试重新生成设计
              </Typography>
            </Box>
          )}
        </>
      ) : (
        <Box sx={{ color: 'white', p: 4 }}>
          <Typography variant="h6">PCB布局可视化</Typography>
          <Typography variant="body2">
            板子尺寸: {layout?.dimensions?.width || 100}mm × {layout?.dimensions?.height || 80}mm
          </Typography>
          <Typography variant="body2">
            层数: {layout?.layers || 2}
          </Typography>
          <Typography variant="body2">
            元件数: {layout?.components?.length || 0}
          </Typography>
        </Box>
      )}
    </Box>
  );

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2, flexWrap: 'wrap', gap: 1 }}>
        <Typography variant="h6" fontWeight="bold">
          PCB布局
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
          <Tooltip title="全屏查看">
            <IconButton onClick={() => setFullscreen(true)} size="small">
              <FullscreenIcon />
            </IconButton>
          </Tooltip>
          <Tooltip title="下载 (Ctrl+S)">
            <span>
              <IconButton onClick={handleDownload} disabled={!image} size="small">
                <DownloadIcon />
              </IconButton>
            </span>
          </Tooltip>
        </Box>
      </Box>

      {/* PCB Display */}
      <Paper elevation={1} sx={{ p: 2 }}>
        {pcbImage}
      </Paper>

      {/* PCB Info */}
      {layout && (
        <Box sx={{ mt: 2 }}>
          <Grid container spacing={2}>
            <Grid item xs={6} md={3}>
              <Typography variant="subtitle2" color="text.secondary">
                板子尺寸
              </Typography>
              <Typography variant="body1">
                {layout.dimensions?.width || 100}mm × {layout.dimensions?.height || 80}mm
              </Typography>
            </Grid>
            <Grid item xs={6} md={3}>
              <Typography variant="subtitle2" color="text.secondary">
                层数
              </Typography>
              <Typography variant="body1">
                {layout.layers || 2} 层
              </Typography>
            </Grid>
            <Grid item xs={6} md={3}>
              <Typography variant="subtitle2" color="text.secondary">
                元件数
              </Typography>
              <Typography variant="body1">
                {layout.layout?.components?.length || layout.components?.length || 0} 个
              </Typography>
            </Grid>
            <Grid item xs={6} md={3}>
              <Typography variant="subtitle2" color="text.secondary">
                走线数
              </Typography>
              <Typography variant="body1">
                {layout.layout?.tracks?.length || 0} 条
              </Typography>
            </Grid>
          </Grid>
        </Box>
      )}

      {/* Fullscreen Dialog */}
      <Dialog
        open={fullscreen}
        onClose={() => setFullscreen(false)}
        maxWidth="xl"
        fullWidth
        PaperProps={{
          sx: { height: '90vh' }
        }}
      >
        <DialogTitle>PCB布局 - 全屏查看</DialogTitle>
        <DialogContent>
          {pcbImage}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setFullscreen(false)}>关闭</Button>
        </DialogActions>
      </Dialog>

      {/* Info */}
      <Box sx={{ mt: 2 }}>
        <Typography variant="body2" color="text.secondary">
          💡 提示：绿色区域代表铜走线，元件以黑色矩形显示。使用缩放按钮获得更好的视觉效果（支持Ctrl+S快捷下载）。
        </Typography>
      </Box>
    </Box>
  );
}
