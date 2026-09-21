"use client";

import React, { useEffect, useMemo, useRef, useState } from 'react';
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
import FitScreenIcon from '@mui/icons-material/FitScreen';
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
  const containerRef = useRef(null);
  const userZoomedRef = useRef(false);

  const isPaged = Boolean(pages && pages.pages && pages.pages.length > 0);
  const pageList = isPaged ? pages.pages : [];
  const currentPage = pageList[pageIndex];
  const currentSvg = isPaged ? (currentPage?.svg || '') : svg;

  // SVG intrinsic aspect from its viewBox; the zoom buttons size the svg as a
  // percentage of container width, so fitting needs the drawing's real shape.
  const svgAspect = useMemo(() => {
    const m = /viewBox="([\d.\-]+)\s+([\d.\-]+)\s+([\d.]+)\s+([\d.]+)"/.exec(currentSvg || '');
    if (!m) return null;
    const w = parseFloat(m[3]);
    const h = parseFloat(m[4]);
    return w > 0 && h > 0 ? w / h : null;
  }, [currentSvg]);

  useEffect(() => {
    setPageIndex(0);
    userZoomedRef.current = false;
  }, [pages, svg]);

  const applyFit = () => {
    const el = containerRef.current;
    if (!el || !svgAspect) return null;
    const { clientWidth: W, clientHeight: H } = el;
    if (!W || !H) return null;
    const pad = 24;
    // rendered width = zoom * W; rendered height = width / aspect
    const fit = Math.min((W - pad) / W, ((H - pad) * svgAspect) / W);
    const clamped = Math.max(0.4, Math.min(3, fit));
    setZoom(clamped);
    return clamped;
  };

  // Fit on mount / page change / container resize until the user zooms
  // manually; afterwards their choice wins.
  useEffect(() => {
    if (!svgAspect) return undefined;
    applyFit();
    const el = containerRef.current;
    if (!el || typeof ResizeObserver === 'undefined') return undefined;
    const ro = new ResizeObserver(() => {
      if (!userZoomedRef.current) applyFit();
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [svgAspect, pageIndex]);

  const handleZoomIn = () => {
    userZoomedRef.current = true;
    setZoom(prev => Math.min(prev + 0.2, 3));
  };

  const handleZoomOut = () => {
    userZoomedRef.current = true;
    setZoom(prev => Math.max(prev - 0.2, 0.4));
  };

  const handleFit = () => {
    userZoomedRef.current = false;
    applyFit();
  };

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
          <Tooltip title="Fit to view">
            <IconButton onClick={handleFit} size="small">
              <FitScreenIcon />
            </IconButton>
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
        ref={containerRef}
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
