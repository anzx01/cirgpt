"use client";

import React, { useEffect, useState } from 'react';
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
import { downloadSVG } from '../lib/downloadUtils';

export default function SchematicViewer({ svg }) {
  const [zoom, setZoom] = useState(1);
  const [error, setError] = useState(null);

  const handleZoomIn = () => {
    setZoom(prev => Math.min(prev + 0.2, 3));
  };

  const handleZoomOut = () => {
    setZoom(prev => Math.max(prev - 0.2, 0.4));
  };

  const handleDownload = () => {
    if (!svg) {
      setError('No schematic SVG is available to download.');
      return;
    }

    const result = downloadSVG(svg, 'schematic.svg');
    if (!result.success) {
      setError('Download failed. Please try again.');
    }
  };

  useEffect(() => {
    const handleKeyPress = event => {
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
          Schematic has not been generated yet. Please wait for design generation to finish.
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
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6" fontWeight="bold">
          Circuit Schematic
        </Typography>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          <Tooltip title="Zoom out">
            <span>
              <IconButton onClick={handleZoomOut} disabled={zoom <= 0.4} size="small">
                <ZoomOutIcon />
              </IconButton>
            </span>
          </Tooltip>
          <Typography variant="body2" sx={{ minWidth: 50, textAlign: 'center' }}>
            {Math.round(zoom * 100)}%
          </Typography>
          <Tooltip title="Zoom in">
            <span>
              <IconButton onClick={handleZoomIn} disabled={zoom >= 3} size="small">
                <ZoomInIcon />
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title="Download SVG (Ctrl+S)">
            <IconButton onClick={handleDownload} size="small">
              <DownloadIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

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
          dangerouslySetInnerHTML={{ __html: svg }}
          sx={{
            width: '100%',
            minHeight: { xs: 350, md: 500 },
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            '& svg': {
              display: 'block',
              width: `${zoom * 100}%`,
              maxWidth: 'none',
              height: 'auto'
            }
          }}
        />
      </Paper>

      <Box sx={{ mt: 2 }}>
        <Typography variant="body2" color="text.secondary">
          Use the zoom controls to inspect the schematic, or download the KiCad-exported SVG.
        </Typography>
      </Box>
    </Box>
  );
}
