"use client";

import React, { useEffect, useRef, useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Alert,
  Button,
  IconButton,
  Tooltip
} from '@mui/material';
import ZoomInIcon from '@mui/icons-material/ZoomIn';
import ZoomOutIcon from '@mui/icons-material/ZoomOut';
import DownloadIcon from '@mui/icons-material/Download';
import { SVG } from '@svgdotjs/svg.js';

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

    } catch (err) {
      setError('Failed to render schematic');
      console.error(err);
    }
  }, [svg, zoom]);

  const handleZoomIn = () => {
    setZoom(prev => Math.min(prev + 0.2, 3));
  };

  const handleZoomOut = () => {
    setZoom(prev => Math.max(prev - 0.2, 0.4));
  };

  const handleDownload = () => {
    if (!svg) return;

    const blob = new Blob([svg], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'schematic.svg';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  if (!svg) {
    return (
      <Box sx={{ p: 4, textAlign: 'center' }}>
        <Alert severity="info">
          No schematic available yet. Please wait for generation to complete.
        </Alert>
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error">{error}</Alert>
    );
  }

  return (
    <Box>
      {/* Toolbar */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6" fontWeight="bold">
          Circuit Schematic
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
          <Tooltip title="Download SVG">
            <IconButton onClick={handleDownload}>
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
          height: 600,
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
            minHeight: 500,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}
        />
      </Paper>

      {/* Info */}
      <Box sx={{ mt: 2 }}>
        <Typography variant="body2" color="text.secondary">
          💡 Tip: Use the zoom buttons to zoom in/out. Click download to save the schematic as SVG.
        </Typography>
      </Box>
    </Box>
  );
}
