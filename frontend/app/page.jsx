"use client";

import React from 'react';
import { useRouter } from 'next/navigation';
import {
  Container,
  Box,
  Typography,
  Button,
  Grid,
  Card,
  CardContent,
  CardActions
} from '@mui/material';
import {
  AutoAwesome as AIIcon,
  Schema as SchemaIcon,
  ViewInAr as PcbIcon,
  ArrowForward as ArrowIcon
} from '@mui/icons-material';

export default function Home() {
  const router = useRouter();

  const features = [
    {
      icon: <AIIcon sx={{ fontSize: 40, color: 'primary.main' }} />,
      title: 'AI-Powered Design',
      description: 'Describe your circuit in natural language and let AI create it for you'
    },
    {
      icon: <SchemaIcon sx={{ fontSize: 40, color: 'secondary.main' }} />,
      title: 'Automatic Schematics',
      description: 'Generate circuit schematics automatically with interactive visualization'
    },
    {
      icon: <PcbIcon sx={{ fontSize: 40, color: 'success.main' }} />,
      title: 'Smart PCB Layout',
      description: 'Get optimized PCB layouts with component placement and routing'
    }
  ];

  return (
    <Container maxWidth="lg" sx={{ py: 8 }}>
      {/* Hero Section */}
      <Box sx={{ textAlign: 'center', mb: 12 }}>
        <Typography
          variant="h2"
          component="h1"
          gutterBottom
          fontWeight="bold"
          sx={{
            background: 'linear-gradient(45deg, #1976d2 30%, #42a5f5 90%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            mb: 3
          }}
        >
          AI Circuit Designer
        </Typography>
        <Typography variant="h5" color="text.secondary" paragraph sx={{ maxWidth: 700, mx: 'auto' }}>
          Transform your ideas into complete circuit designs in seconds.
          Just describe what you want, and watch AI do the magic.
        </Typography>
        <Button
          variant="contained"
          size="large"
          endIcon={<ArrowIcon />}
          onClick={() => router.push('/design')}
          sx={{
            mt: 4,
            px: 4,
            py: 1.5,
            fontSize: '1.2rem',
            textTransform: 'none',
            borderRadius: 2
          }}
        >
          Start Designing Now
        </Button>
      </Box>

      {/* Features Section */}
      <Grid container spacing={4} sx={{ mb: 12 }}>
        {features.map((feature, index) => (
          <Grid item xs={12} md={4} key={index}>
            <Card
              sx={{
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                transition: 'transform 0.2s',
                '&:hover': {
                  transform: 'translateY(-8px)',
                  boxShadow: 4
                }
              }}
            >
              <CardContent sx={{ flexGrow: 1, textAlign: 'center' }}>
                <Box sx={{ mb: 2 }}>
                  {feature.icon}
                </Box>
                <Typography variant="h6" component="h3" gutterBottom fontWeight="bold">
                  {feature.title}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {feature.description}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      {/* How It Works Section */}
      <Box sx={{ textAlign: 'center', mb: 8 }}>
        <Typography variant="h4" gutterBottom fontWeight="bold">
          How It Works
        </Typography>
        <Typography variant="body1" color="text.secondary" paragraph>
          Three simple steps to your custom circuit
        </Typography>
      </Box>

      <Grid container spacing={3} sx={{ mb: 12 }}>
        {[
          { step: '1', title: 'Describe', desc: 'Type your circuit requirements in plain English' },
          { step: '2', title: 'Generate', desc: 'AI creates schematic, simulation, PCB, and BOM' },
          { step: '3', title: 'Download', desc: 'Export your design files for manufacturing' }
        ].map((item) => (
          <Grid item xs={12} md={4} key={item.step}>
            <Box
              sx={{
                textAlign: 'center',
                p: 3,
                bgcolor: 'background.paper',
                borderRadius: 2,
                boxShadow: 1
              }}
            >
              <Box
                sx={{
                  width: 60,
                  height: 60,
                  borderRadius: '50%',
                  bgcolor: 'primary.main',
                  color: 'white',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  mx: 'auto',
                  mb: 2,
                  fontSize: '1.5rem',
                  fontWeight: 'bold'
                }}
              >
                {item.step}
              </Box>
              <Typography variant="h6" gutterBottom fontWeight="bold">
                {item.title}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {item.desc}
              </Typography>
            </Box>
          </Grid>
        ))}
      </Grid>

      {/* CTA Section */}
      <Box
        sx={{
          bgcolor: 'primary.main',
          color: 'white',
          borderRadius: 4,
          p: 6,
          textAlign: 'center',
          mb: 8
        }}
      >
        <Typography variant="h4" gutterBottom fontWeight="bold">
          Ready to Create Your Circuit?
        </Typography>
        <Typography variant="body1" paragraph sx={{ mb: 4, opacity: 0.9 }}>
          Join thousands of engineers and hobbyists using AI to accelerate their designs
        </Typography>
        <Button
          variant="contained"
          size="large"
          endIcon={<ArrowIcon />}
          onClick={() => router.push('/design')}
          sx={{
            bgcolor: 'white',
            color: 'primary.main',
            px: 4,
            py: 1.5,
            fontSize: '1.1rem',
            textTransform: 'none',
            borderRadius: 2,
            '&:hover': {
              bgcolor: 'grey.100'
            }
          }}
        >
          Get Started Free
        </Button>
      </Box>
    </Container>
  );
}
