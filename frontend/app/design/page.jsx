"use client";

import React, { useState } from 'react';
import {
  Container,
  Box,
  Typography,
  TextField,
  Button,
  Paper,
  CircularProgress,
  Alert,
  Chip
} from '@mui/material';
import { useRouter } from 'next/navigation';
import SendIcon from '@mui/icons-material/Send';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';

const examplePrompts = [
  "Design a 555 timer LED blinker circuit with 1 Hz frequency",
  "Create an inverting amplifier with gain of 10 using op-amp",
  "Design a power supply with 5V output from 12V input",
  "Create a low-pass RC filter with cutoff frequency 1kHz"
];

export default function DesignPage() {
  const router = useRouter();
  const [description, setDescription] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!description.trim()) {
      setError('Please enter a circuit description');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      // Create circuit design
      const response = await fetch('http://localhost:8000/api/circuit/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ description }),
      });

      if (!response.ok) {
        throw new Error('Failed to create circuit design');
      }

      const data = await response.json();

      // Start generation
      const genResponse = await fetch(
        `http://localhost:8000/api/circuit/${data.id}/generate`,
        { method: 'POST' }
      );

      if (!genResponse.ok) {
        throw new Error('Failed to start generation');
      }

      // Redirect to results page
      router.push(`/design/${data.id}`);

    } catch (err) {
      setError(err.message);
      setIsSubmitting(false);
    }
  };

  const handleExampleClick = (example) => {
    setDescription(example);
  };

  return (
    <Container maxWidth="lg" sx={{ py: 8 }}>
      <Box sx={{ textAlign: 'center', mb: 6 }}>
        <AutoAwesomeIcon
          sx={{ fontSize: 60, color: 'primary.main', mb: 2 }}
        />
        <Typography variant="h3" component="h1" gutterBottom fontWeight="bold">
          AI Circuit Designer
        </Typography>
        <Typography variant="h6" color="text.secondary">
          Describe your circuit in plain English and watch it come to life
        </Typography>
      </Box>

      <Paper
        elevation={3}
        sx={{
          p: 4,
          maxWidth: 800,
          mx: 'auto',
          borderRadius: 2
        }}
      >
        <form onSubmit={handleSubmit}>
          <Typography variant="h5" gutterBottom fontWeight="bold">
            What circuit would you like to design?
          </Typography>

          <TextField
            fullWidth
            multiline
            rows={6}
            variant="outlined"
            placeholder="Describe your circuit in natural language...&#10;&#10;Example: Design a 555 timer LED blinker circuit that blinks at 1 Hz frequency using a 9V power supply"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            disabled={isSubmitting}
            sx={{
              mt: 3,
              mb: 3,
              '& .MuiOutlinedInput-root': {
                fontSize: '1.1rem'
              }
            }}
          />

          <Box sx={{ mb: 3 }}>
            <Typography variant="subtitle2" color="text.secondary" gutterBottom>
              Or try these examples:
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              {examplePrompts.map((prompt, index) => (
                <Chip
                  key={index}
                  label={prompt.substring(0, 40) + '...'}
                  onClick={() => handleExampleClick(prompt)}
                  clickable
                  disabled={isSubmitting}
                  variant="outlined"
                  size="small"
                  sx={{
                    '&:hover': {
                      bgcolor: 'primary.light',
                      color: 'white'
                    }
                  }}
                />
              ))}
            </Box>
          </Box>

          {error && (
            <Alert severity="error" sx={{ mb: 3 }}>
              {error}
            </Alert>
          )}

          <Button
            type="submit"
            variant="contained"
            size="large"
            fullWidth
            disabled={isSubmitting || !description.trim()}
            startIcon={isSubmitting ? <CircularProgress size={20} /> : <SendIcon />}
            sx={{
              py: 1.5,
              fontSize: '1.1rem',
              fontWeight: 'bold',
              textTransform: 'none'
            }}
          >
            {isSubmitting ? 'Creating Design...' : 'Generate Circuit'}
          </Button>
        </form>
      </Paper>

      <Box sx={{ mt: 6, textAlign: 'center' }}>
        <Typography variant="body2" color="text.secondary">
          The AI will generate a complete circuit design including: schematic, simulation,
          PCB layout, and bill of materials
        </Typography>
      </Box>
    </Container>
  );
}
