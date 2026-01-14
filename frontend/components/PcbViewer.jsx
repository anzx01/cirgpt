"use client";

import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Alert,
  Button,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Grid
} from '@mui/material';
import ZoomInIcon from '@mui/icons-material/ZoomIn';
import ZoomOutIcon from '@mui/icons-material/ZoomOut';
import FullscreenIcon from '@mui/icons-material/Fullscreen';
import DownloadIcon from '@mui/icons-material/Download';

export default function PcbViewer({ layout, image }) {
  const [zoom, setZoom] = useState(1);
  const [fullscreen, setFullscreen] = useState(false);
  const [imageError, setImageError] = useState(false);

  // Debug: log the image prop
  useEffect(() => {
    if (image) {
      console.log('PCB Image data type:', typeof image);
      console.log('PCB Image length:', image?.length);
      console.log('PCB Image prefix:', image?.substring(0, 50));
    }
  }, [image]);

  if (!layout && !image) {
    return (
      <Box sx={{ p: 4, textAlign: 'center' }}>
        <Alert severity="info">
          No PCB layout available yet. Please wait for generation to complete.
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
    if (!image) return;

    try {
      let blob, filename;

      // Check if it's SVG
      if (image.trim().startsWith('<svg') || image.includes('<svg')) {
        // Extract SVG content if wrapped in data URL
        let svgContent = image;
        if (image.startsWith('data:image/svg+xml,')) {
          svgContent = decodeURIComponent(image.split(',')[1]);
        } else if (image.startsWith('data:image')) {
          svgContent = image.split(',')[1];
        }

        blob = new Blob([svgContent], { type: 'image/svg+xml' });
        filename = 'pcb-layout.svg';
      } else {
        // Handle PNG/base64
        let base64Data = image;
        if (image.startsWith('data:image')) {
          base64Data = image.split(',')[1];
        }

        const byteCharacters = atob(base64Data);
        const byteNumbers = new Array(byteCharacters.length);
        for (let i = 0; i < byteCharacters.length; i++) {
          byteNumbers[i] = byteCharacters.charCodeAt(i);
        }
        const byteArray = new Uint8Array(byteNumbers);
        blob = new Blob([byteArray], { type: 'image/png' });
        filename = 'pcb-layout.png';
      }

      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Download failed:', error);
      alert('Failed to download PCB layout image');
    }
  };

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
        height: fullscreen ? '80vh' : 600,
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
              console.error('Image failed to load');
              console.error('Image src:', getImageSrc(image)?.substring(0, 100));
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
                Failed to load PCB layout image
              </Alert>
              <Typography variant="body2" sx={{ color: 'white' }}>
                Check browser console for details
              </Typography>
            </Box>
          )}
        </>
      ) : (
        <Box sx={{ color: 'white', p: 4 }}>
          <Typography variant="h6">PCB Layout Visualization</Typography>
          <Typography variant="body2">
            Board Dimensions: {layout?.dimensions?.width || 100}mm × {layout?.dimensions?.height || 80}mm
          </Typography>
          <Typography variant="body2">
            Layers: {layout?.layers || 2}
          </Typography>
          <Typography variant="body2">
            Components: {layout?.components?.length || 0}
          </Typography>
        </Box>
      )}
    </Box>
  );

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6" fontWeight="bold">
          PCB Layout
        </Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Tooltip title="Zoom Out">
            <IconButton onClick={handleZoomOut} disabled={zoom <= 0.4}>
              <ZoomOutIcon />
            </IconButton>
          </Tooltip>
          <Typography variant="body2" sx={{ display: 'flex', alignItems: 'center', mx: 1 }}>
            {Math.round(zoom * 100)}%
          </Typography>
          <Tooltip title="Zoom In">
            <IconButton onClick={handleZoomIn} disabled={zoom >= 3}>
              <ZoomInIcon />
            </IconButton>
          </Tooltip>
          <Tooltip title="Fullscreen">
            <IconButton onClick={() => setFullscreen(true)}>
              <FullscreenIcon />
            </IconButton>
          </Tooltip>
          <Tooltip title="Download">
            <IconButton onClick={handleDownload} disabled={!image}>
              <DownloadIcon />
            </IconButton>
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
            <Grid item xs={12} md={6}>
              <Typography variant="subtitle2" color="text.secondary">
                Board Size
              </Typography>
              <Typography variant="body1">
                {layout.dimensions?.width || 100}mm × {layout.dimensions?.height || 80}mm
              </Typography>
            </Grid>
            <Grid item xs={12} md={6}>
              <Typography variant="subtitle2" color="text.secondary">
                Layers
              </Typography>
              <Typography variant="body1">
                {layout.layers || 2} layers
              </Typography>
            </Grid>
            <Grid item xs={12} md={6}>
              <Typography variant="subtitle2" color="text.secondary">
                Components
              </Typography>
              <Typography variant="body1">
                {layout.layout?.components?.length || layout.components?.length || 0} components
              </Typography>
            </Grid>
            <Grid item xs={12} md={6}>
              <Typography variant="subtitle2" color="text.secondary">
                Tracks
              </Typography>
              <Typography variant="body1">
                {layout.layout?.tracks?.length || 0} routes
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
      >
        <DialogTitle>PCB Layout - Fullscreen</DialogTitle>
        <DialogContent>
          {pcbImage}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setFullscreen(false)}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* Info */}
      <Box sx={{ mt: 2 }}>
        <Typography variant="body2" color="text.secondary">
          💡 Tip: Green areas represent copper traces. Components are shown as black rectangles.
          Use zoom buttons for better visibility.
        </Typography>
      </Box>
    </Box>
  );
}
