"use client";

import React, { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import {
  Container,
  Box,
  Typography,
  Paper,
  Grid,
  LinearProgress,
  Chip,
  Button,
  Alert,
  Tabs,
  Tab,
  CircularProgress,
  Stack,
  Divider
} from '@mui/material';
import {
  Description as DescriptionIcon,
  ShowChart as SimulationIcon,
  ViewInAr as PcbIcon,
  Checklist as BomIcon,
  Home as HomeIcon,
  FactCheck as ValidationIcon,
  Download as DownloadIcon
} from '@mui/icons-material';
import { io } from 'socket.io-client';
import SchematicViewer from '../../../components/SchematicViewer';
import SimulationViewer from '../../../components/SimulationViewer';
import PcbViewer from '../../../components/PcbViewer';
import BomViewer from '../../../components/BomViewer';
import { API_BASE_URL, WEBSOCKET_URL } from '../../../config.mjs';

function TabPanel({ children, value, index }) {
  return (
    <div role="tabpanel" hidden={value !== index}>
      {value === index && <Box sx={{ py: 3 }}>{children}</Box>}
    </div>
  );
}

export default function DesignResultPage() {
  const params = useParams();
  const router = useRouter();
  const designId = params.id;

  const [design, setDesign] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [tabValue, setTabValue] = useState(0);
  const [progress, setProgress] = useState({
    message: 'Initializing...',
    progress: 0,
    status: 'pending'
  });

  // Fetch design data - unified polling logic
  useEffect(() => {
    const fetchDesign = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/circuit/${designId}`);

        if (!response.ok) {
          throw new Error('Failed to fetch design');
        }

        const data = await response.json();
        setDesign(data);
        setLoading(false);

        // Update progress based on status
        if (data.status === 'completed') {
          setProgress({
            message: 'Design generation complete!',
            progress: data.progress ?? 100,
            status: 'completed'
          });
          return true; // Signal to stop polling
        } else if (data.status === 'failed') {
          setProgress({
            message: `Error: ${data.error_message || 'Generation failed'}`,
            progress: data.progress ?? 0,
            status: 'failed'
          });
          setError(data.error_message);
          return true; // Signal to stop polling
        } else if (data.status === 'processing') {
          setProgress({
            message: data.current_step || 'Processing...',
            progress: data.progress ?? 50,
            status: 'processing'
          });
          return false; // Continue polling
        } else if (data.status === 'pending') {
          setProgress({
            message: data.current_step || 'Waiting to start...',
            progress: data.progress ?? 10,
            status: 'pending'
          });
          return false; // Continue polling
        }
        return false; // Continue polling for unknown states
      } catch (err) {
        console.error('Fetch error:', err);
        setError(err.message);
        setLoading(false);
        return true; // Stop polling on error
      }
    };

    // Initial fetch
    fetchDesign();

    // Set up polling for non-completed states
    const pollInterval = setInterval(async () => {
      const shouldStop = await fetchDesign();
      if (shouldStop) {
        clearInterval(pollInterval);
      }
    }, 2000); // Poll every 2 seconds

    return () => {
      clearInterval(pollInterval);
    };
  }, [designId]);

  useEffect(() => {
    const socket = io(WEBSOCKET_URL, {
      path: '/socket.io',
      transports: ['websocket', 'polling']
    });

    socket.on('connect', () => {
      socket.emit('subscribe', { design_id: Number(designId) });
    });

    socket.on('design.progress', (event) => {
      setProgress({
        message: event.message,
        progress: event.progress,
        status: 'processing'
      });
    });

    socket.on('design.completed', () => {
      setProgress({
        message: 'Design generation complete!',
        progress: 100,
        status: 'completed'
      });
    });

    socket.on('design.failed', (event) => {
      setProgress({
        message: event.message,
        progress: event.progress ?? 0,
        status: 'failed'
      });
      setError(event.message);
    });

    return () => {
      socket.emit('unsubscribe', { design_id: Number(designId) });
      socket.disconnect();
    };
  }, [designId]);

  const handleTabChange = (event, newValue) => {
    setTabValue(newValue);
  };

  const handleArtifactDownload = (artifactId) => {
    window.open(`${API_BASE_URL}/circuit/${designId}/artifacts/${artifactId}`, '_blank', 'noopener,noreferrer');
  };

  if (loading) {
    return (
      <Container maxWidth="lg" sx={{ py: 8 }}>
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 400 }}>
          <CircularProgress size={60} />
        </Box>
      </Container>
    );
  }

  if (error && progress.status === 'failed') {
    return (
      <Container maxWidth="lg" sx={{ py: 8 }}>
        <Alert severity="error">{error}</Alert>
        <Button
          variant="outlined"
          onClick={() => router.push('/design')}
          sx={{ mt: 2 }}
        >
          Create New Design
        </Button>
      </Container>
    );
  }

  const isProcessing = progress.status === 'processing' || progress.status === 'pending';

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      {/* Header */}
      <Paper elevation={2} sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
          <Box sx={{ flex: 1 }}>
            <Typography variant="h4" fontWeight="bold" gutterBottom>
              Circuit Design #{designId}
            </Typography>
            <Typography variant="body1" color="text.secondary" paragraph>
              {design?.description}
            </Typography>
          </Box>
          <Button
            variant="outlined"
            startIcon={<HomeIcon />}
            onClick={() => router.push('/')}
            sx={{ ml: 2 }}
          >
            Back to Home
          </Button>
        </Box>

        {isProcessing && (
          <Box sx={{ mt: 2 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
              <Typography variant="body2" color="text.secondary">
                {progress.message}
              </Typography>
              <Typography variant="body2" color="primary" fontWeight="bold">
                {progress.progress}%
              </Typography>
            </Box>
            <LinearProgress
              variant="determinate"
              value={progress.progress}
              sx={{ height: 10, borderRadius: 5 }}
            />
          </Box>
        )}

        {!isProcessing && progress.status === 'completed' && (
          <Alert severity="success" sx={{ mt: 2 }}>
            Design generation completed successfully!
          </Alert>
        )}
      </Paper>

      {/* Results Tabs */}
      <Paper elevation={2} sx={{ mb: 3 }}>
        <Tabs
          value={tabValue}
          onChange={handleTabChange}
          variant="fullWidth"
          sx={{ borderBottom: 1, borderColor: 'divider' }}
        >
          <Tab
            icon={<DescriptionIcon />}
            label="Schematic"
            disabled={isProcessing}
          />
          <Tab
            icon={<SimulationIcon />}
            label="Simulation"
            disabled={isProcessing || !design?.simulation_results}
          />
          <Tab
            icon={<PcbIcon />}
            label="PCB Layout"
            disabled={isProcessing || !design?.pcb_layout}
          />
          <Tab
            icon={<BomIcon />}
            label="Bill of Materials"
            disabled={isProcessing || !design?.bom}
          />
          <Tab
            icon={<ValidationIcon />}
            label="Validation"
            disabled={isProcessing || !design?.validation}
          />
        </Tabs>

        <TabPanel value={tabValue} index={0}>
          <SchematicViewer svg={design?.schematic_svg} />
        </TabPanel>

        <TabPanel value={tabValue} index={1}>
          <SimulationViewer results={design?.simulation_results} />
        </TabPanel>

        <TabPanel value={tabValue} index={2}>
          <PcbViewer layout={design?.pcb_layout} image={design?.pcb_image} />
        </TabPanel>

        <TabPanel value={tabValue} index={3}>
          <BomViewer bom={design?.bom} />
        </TabPanel>

        <TabPanel value={tabValue} index={4}>
          <Box sx={{ px: 3 }}>
            <Typography variant="h6" fontWeight="bold" gutterBottom>
              Validation Report
            </Typography>
            <Alert severity={design?.validation?.status === 'passed' ? 'success' : 'warning'} sx={{ mb: 2 }}>
              Status: <strong>{design?.validation?.status || 'unknown'}</strong>
            </Alert>

            <Grid container spacing={2} sx={{ mb: 3 }}>
              {Object.entries(design?.validation?.checks || {}).map(([key, value]) => (
                <Grid item xs={12} md={6} key={key}>
                  <Paper elevation={0} sx={{ p: 2, border: '1px solid', borderColor: 'divider' }}>
                    <Typography variant="caption" color="text.secondary">
                      {key}
                    </Typography>
                    <Typography variant="body1">{String(value)}</Typography>
                  </Paper>
                </Grid>
              ))}
            </Grid>

            {design?.validation?.warnings?.length > 0 && (
              <Alert severity="warning" sx={{ mb: 3 }}>
                <Stack spacing={1}>
                  {design.validation.warnings.map((warning, index) => (
                    <Typography variant="body2" key={index}>{warning}</Typography>
                  ))}
                </Stack>
              </Alert>
            )}

            <Divider sx={{ my: 3 }} />

            <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
              Artifacts
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              {Object.entries(design?.artifacts || {}).map(([artifactId, artifact]) => (
                <Button
                  key={artifactId}
                  variant="outlined"
                  startIcon={<DownloadIcon />}
                  onClick={() => handleArtifactDownload(artifactId)}
                >
                  {artifact.filename || artifactId}
                </Button>
              ))}
            </Box>
          </Box>
        </TabPanel>
      </Paper>

      {/* Actions */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button
            variant="outlined"
            startIcon={<HomeIcon />}
            onClick={() => router.push('/')}
          >
            Back to Home
          </Button>
          <Button
            variant="contained"
            onClick={() => router.push('/design')}
          >
            Create New Design
          </Button>
        </Box>
        {!isProcessing && (
          <Chip
            label={`Estimated Cost: $${design?.estimated_cost?.toFixed(2) || '0.00'}`}
            color="success"
            size="medium"
          />
        )}
      </Box>
    </Container>
  );
}
