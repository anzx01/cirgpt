"use client";

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Container,
  Grid,
  Paper,
  Stack,
  TextField,
  Typography
} from '@mui/material';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import SendIcon from '@mui/icons-material/Send';
import { API_BASE_URL } from '../config.mjs';

const examplePrompts = [
  'Design a 555 timer LED blinker circuit with 1 Hz frequency and 9V supply',
  'Create an inverting op-amp amplifier with gain of 10',
  'Design a simple LED circuit with 5V supply and 20mA current',
  'Create a low-pass RC filter with cutoff frequency 1kHz'
];

const supportedTypes = ['LED limiter', 'RC low-pass', '555 blinker', 'Op-amp amplifier'];

export default function DesignWorkbench() {
  const router = useRouter();
  const [description, setDescription] = useState(examplePrompts[0]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (event) => {
    event.preventDefault();
    const trimmed = description.trim();
    if (!trimmed) {
      setError('Enter a circuit request.');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const createResponse = await fetch(`${API_BASE_URL}/circuit/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ description: trimmed })
      });

      if (!createResponse.ok) {
        throw new Error('Could not create the design.');
      }

      const design = await createResponse.json();
      const generateResponse = await fetch(`${API_BASE_URL}/circuit/${design.id}/generate`, {
        method: 'POST'
      });

      if (!generateResponse.ok) {
        throw new Error('Could not start generation.');
      }

      router.push(`/design/${design.id}`);
    } catch (err) {
      setError(err.message);
      setIsSubmitting(false);
    }
  };

  return (
    <Container maxWidth="xl" sx={{ py: { xs: 3, md: 5 } }}>
      <Grid container spacing={3} alignItems="stretch">
        <Grid item xs={12} lg={5}>
          <Paper elevation={1} sx={{ p: { xs: 2, md: 3 }, height: '100%' }}>
            <Stack spacing={2}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <AutoAwesomeIcon color="primary" />
                <Typography variant="h4" component="h1" fontWeight="bold">
                  CircuitGPT
                </Typography>
              </Box>

              <form onSubmit={handleSubmit}>
                <Stack spacing={2}>
                  <TextField
                    fullWidth
                    multiline
                    minRows={8}
                    label="Circuit request"
                    value={description}
                    onChange={(event) => setDescription(event.target.value)}
                    disabled={isSubmitting}
                  />

                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                    {examplePrompts.map((prompt) => (
                      <Chip
                        key={prompt}
                        label={prompt}
                        onClick={() => setDescription(prompt)}
                        disabled={isSubmitting}
                        variant="outlined"
                        size="small"
                      />
                    ))}
                  </Box>

                  {error && <Alert severity="error">{error}</Alert>}

                  <Button
                    type="submit"
                    variant="contained"
                    size="large"
                    startIcon={isSubmitting ? <CircularProgress size={18} color="inherit" /> : <SendIcon />}
                    disabled={isSubmitting || !description.trim()}
                    sx={{ alignSelf: { xs: 'stretch', sm: 'flex-start' } }}
                  >
                    {isSubmitting ? 'Queued' : 'Generate'}
                  </Button>
                </Stack>
              </form>
            </Stack>
          </Paper>
        </Grid>

        <Grid item xs={12} lg={7}>
          <Paper elevation={1} sx={{ p: { xs: 2, md: 3 }, height: '100%' }}>
            <Stack spacing={2}>
              <Typography variant="h6" fontWeight="bold">
                KiCad-first MVP
              </Typography>
              <Alert severity="info">
                v1 creates verified drafts for a constrained circuit set. PCB output is an experimental preview; Gerber export is disabled until KiCad DRC is integrated.
              </Alert>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {supportedTypes.map((type) => (
                  <Chip key={type} label={type} color="primary" variant="outlined" />
                ))}
              </Box>
              <Box
                sx={{
                  bgcolor: 'grey.50',
                  border: '1px solid',
                  borderColor: 'divider',
                  borderRadius: 1,
                  p: 2
                }}
              >
                <Typography variant="subtitle2" color="text.secondary">
                  Artifacts
                </Typography>
                <Typography variant="body1">
                  CircuitIR, SPICE netlist, SVG schematic, simulation report, BOM CSV, validation JSON, experimental KiCad PCB preview.
                </Typography>
              </Box>
            </Stack>
          </Paper>
        </Grid>
      </Grid>
    </Container>
  );
}
