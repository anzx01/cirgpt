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
  CircularProgress
} from '@mui/material';
import {
  Description as DescriptionIcon,
  ShowChart as SimulationIcon,
  ViewInAr as PcbIcon,
  Checklist as BomIcon
} from '@mui/icons-material';
import { io } from 'socket.io-client';
import SchematicViewer from '../../../components/SchematicViewer';
import SimulationViewer from '../../../components/SimulationViewer';
import PcbViewer from '../../../components/PcbViewer';
import BomViewer from '../../../components/BomViewer';

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

  // Socket.io connection
  useEffect(() => {
    const socket = io('http://localhost:8000', {
      transports: ['websocket', 'polling']
    });

    socket.on('connect', () => {
      console.log('Connected to server');
      socket.emit('subscribe', { design_id: parseInt(designId) });
    });

    socket.on('design_progress', (data) => {
      if (data.design_id === parseInt(designId)) {
        setProgress({
          message: data.message,
          progress: data.progress,
          status: 'processing'
        });
      }
    });

    socket.on('design_complete', (data) => {
      if (data.design_id === parseInt(designId)) {
        setProgress({
          message: 'Design generation complete!',
          progress: 100,
          status: 'completed'
        });
        // Reload design data
        fetchDesign();
      }
    });

    socket.on('design_error', (data) => {
      if (data.design_id === parseInt(designId)) {
        setProgress({
          message: `Error: ${data.message}`,
          progress: 0,
          status: 'failed'
        });
        setError(data.message);
      }
    });

    return () => {
      socket.emit('unsubscribe', { design_id: parseInt(designId) });
      socket.disconnect();
    };
  }, [designId]);

  // Fetch design data
  const fetchDesign = async () => {
    try {
      const response = await fetch(`http://localhost:8000/api/circuit/${designId}`);

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
          progress: 100,
          status: 'completed'
        });
      } else if (data.status === 'failed') {
        setProgress({
          message: `Error: ${data.error_message || 'Generation failed'}`,
          progress: 0,
          status: 'failed'
        });
        setError(data.error_message);
      }

    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDesign();
  }, [designId]);

  const handleTabChange = (event, newValue) => {
    setTabValue(newValue);
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
        <Typography variant="h4" fontWeight="bold" gutterBottom>
          Circuit Design #{designId}
        </Typography>
        <Typography variant="body1" color="text.secondary" paragraph>
          {design?.description}
        </Typography>

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
      </Paper>

      {/* Actions */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
        <Button
          variant="outlined"
          onClick={() => router.push('/design')}
        >
          Create New Design
        </Button>
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
