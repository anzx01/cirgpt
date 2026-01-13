"use client";

import React, { useState } from 'react';
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
  DialogActions
} from '@mui/material';
import ZoomInIcon from '@mui/icons-material/ZoomIn';
import ZoomOutIcon from '@mui/icons-material/ZoomOut';
import FullscreenIcon from '@mui/icons-material/Fullscreen';
import DownloadIcon from '@mui/icons-material/Download';

export default function PcbViewer({ layout, image }) {
  const [zoom, setZoom] = useState(1);
  const [fullscreen, setFullscreen] = useState(false);

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

    // Convert base64 to blob
    const byteCharacters = atob(image);
    const byteNumbers = new Array(byteCharacters.length);
    for (let i = 0; i < byteCharacters.length; i++) {
      byteNumbers[i] = byteCharacters.charCodeAt(i);
    }
    const byteArray = new Uint8Array(byteNumbers);
    const blob = new Blob([byteArray], { type: 'image/png' });

    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'pcb-layout.png';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
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
        <img
          src={`data:image/png;base64,${image}`}
          alt="PCB Layout"
          style={{
            maxWidth: '100%',
            maxHeight: fullscreen ? '100%' : '580px',
            transform: `scale(${zoom})`,
            transition: 'transform 0.3s ease'
          }}
        />
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
