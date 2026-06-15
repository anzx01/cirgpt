"use client";

import React, { useEffect, useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Alert,
  IconButton,
  Tooltip,
  Chip,
  Stack
} from '@mui/material';
import ZoomInIcon from '@mui/icons-material/ZoomIn';
import ZoomOutIcon from '@mui/icons-material/ZoomOut';
import DownloadIcon from '@mui/icons-material/Download';
import { downloadSVG } from '../lib/downloadUtils';

function PageChip({ label, count, active, onClick }) {
  return (
    <Chip
      label={`${label}${count != null ? ` (${count})` : ''}`}
      onClick={onClick}
      color={active ? 'primary' : 'default'}
      variant={active ? 'filled' : 'outlined'}
      sx={{ cursor: 'pointer' }}
      size="small"
    />
  );
}

export default function SchematicViewer({ svg, pages }) {
  const [zoom, setZoom] = useState(1);
  const [error, setError] = useState(null);
  const [pageIndex, setPageIndex] = useState(0);

  const isPaged = Boolean(pages && pages.pages && pages.pages.length > 0);
  const pageList = isPaged ? pages.pages : [];
  const currentPage = pageList[pageIndex];
  const currentSvg = isPaged ? (currentPage?.svg || '') : svg;

  useEffect(() => {
    setPageIndex(0);
  }, [pages, svg]);

  const handleZoomIn = () => setZoom(prev => Math.min(prev + 0.2, 3));
  const handleZoomOut = () => setZoom(prev => Math.max(prev - 0.2, 0.4));

  const handleDownload = () => {
    if (!currentSvg) {
      setError('No schematic SVG is available to download.');
      return;
    }
    const baseName = isPaged
      ? `schematic_${(currentPage?.subsystem || 'page').replace(/[^a-z0-9_-]/gi, '_')}.svg`
      : 'schematic.svg';
    const result = downloadSVG(currentSvg, baseName);
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
  }, [currentSvg]);

  if (!currentSvg && !isPaged) {
    return (
      <Box sx={{ p: 4, textAlign: 'center' }}>
        <Alert severity="info">
          Schematic has not been generated yet. Please wait for design generation to finish.
        </Alert>
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2, flexWrap: 'wrap', gap: 1 }}>
        <Box>
          <Typography variant="h6" fontWeight="bold">
            Circuit Schematic
            {isPaged && pages.layout === 'subsystem-paged' && (
              <Typography component="span" variant="caption" color="primary" sx={{ ml: 1 }}>
                subsystem-paged ({pages.summary?.subsystem_count ?? pageList.length} layers)
              </Typography>
            )}
          </Typography>
          {isPaged && currentPage?.purpose && (
            <Typography variant="body2" color="text.secondary">
              {currentPage.purpose}
            </Typography>
          )}
        </Box>
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

      {isPaged && (
        <Box sx={{ mb: 2 }}>
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            {pageList.map((page, index) => (
              <PageChip
                key={`${page.subsystem || 'page'}_${index}`}
                label={page.subsystem === '_overview' ? 'Overview' : (page.subsystem || `Page ${index + 1}`)}
                count={page.components ? page.components.length : null}
                active={index === pageIndex}
                onClick={() => setPageIndex(index)}
              />
            ))}
          </Stack>
        </Box>
      )}

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
          dangerouslySetInnerHTML={{ __html: currentSvg }}
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
          {isPaged
            ? 'Each subsystem is rendered on its own page. Use the chips above to switch layers; the overview page lists every layer with its components and any open questions.'
            : 'Use the zoom controls to inspect the schematic, or download the KiCad-exported SVG.'}
        </Typography>
      </Box>
    </Box>
  );
}
