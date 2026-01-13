"use client";

import React, { useMemo } from 'react';
import {
  Box,
  Paper,
  Typography,
  Grid,
  Card,
  CardContent,
  Alert
} from '@mui/material';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts';

export default function SimulationViewer({ results }) {
  if (!results) {
    return (
      <Box sx={{ p: 4, textAlign: 'center' }}>
        <Alert severity="info">
          No simulation results available yet. Please wait for generation to complete.
        </Alert>
      </Box>
    );
  }

  const { time, voltages, currents, summary } = results;

  // Prepare chart data
  const chartData = useMemo(() => {
    if (!time || !voltages) return [];

    const voltageData = voltages.output || voltages.Vout || [];
    const inputData = voltages.input || voltages.Vin || [];
    const currentData = currents?.total || [];

    return time.map((t, i) => ({
      time: Number(t.toFixed(6)),
      output: Number((voltageData[i] || 0).toFixed(3)),
      input: inputData[i] !== undefined ? Number((inputData[i] || 0).toFixed(3)) : null,
      current: currentData[i] !== undefined ? Number((currentData[i] * 1000).toFixed(3)) : null // Convert to mA
    })).filter(point => point.time >= 0); // Filter valid points
  }, [time, voltages, currents]);

  // Calculate statistics
  const stats = useMemo(() => {
    if (!chartData.length) return null;

    const outputVoltages = chartData.map(d => d.output);
    const vMax = Math.max(...outputVoltages);
    const vMin = Math.min(...outputVoltages);
    const vAvg = outputVoltages.reduce((a, b) => a + b, 0) / outputVoltages.length;

    return {
      vMax: vMax.toFixed(2),
      vMin: vMin.toFixed(2),
      vAvg: vAvg.toFixed(2),
      vPeakToPeak: (vMax - vMin).toFixed(2),
      frequency: summary?.estimated_frequency?.toFixed(2) || 'N/A'
    };
  }, [chartData, summary]);

  return (
    <Box>
      {/* Header */}
      <Typography variant="h6" fontWeight="bold" gutterBottom>
        Circuit Simulation Results
      </Typography>

      {/* Statistics Cards */}
      {stats && (
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={6} md={2.4}>
            <Card>
              <CardContent>
                <Typography variant="caption" color="text.secondary">
                  Max Voltage
                </Typography>
                <Typography variant="h6" color="primary">
                  {stats.vMax} V
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={6} md={2.4}>
            <Card>
              <CardContent>
                <Typography variant="caption" color="text.secondary">
                  Min Voltage
                </Typography>
                <Typography variant="h6" color="primary">
                  {stats.vMin} V
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={6} md={2.4}>
            <Card>
              <CardContent>
                <Typography variant="caption" color="text.secondary">
                  Avg Voltage
                </Typography>
                <Typography variant="h6" color="primary">
                  {stats.vAvg} V
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={6} md={2.4}>
            <Card>
              <CardContent>
                <Typography variant="caption" color="text.secondary">
                  Peak-to-Peak
                </Typography>
                <Typography variant="h6" color="primary">
                  {stats.vPeakToPeak} V
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={6} md={2.4}>
            <Card>
              <CardContent>
                <Typography variant="caption" color="text.secondary">
                  Frequency
                </Typography>
                <Typography variant="h6" color="primary">
                  {stats.frequency} Hz
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Waveform Chart */}
      <Paper elevation={1} sx={{ p: 2, mb: 2 }}>
        <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
          Voltage Waveforms
        </Typography>
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="time"
              label={{ value: 'Time (s)', position: 'insideBottomRight', offset: -5 }}
            />
            <YAxis
              label={{ value: 'Voltage (V)', angle: -90, position: 'insideLeft' }}
            />
            <Tooltip />
            <Legend />
            <Line
              type="monotone"
              dataKey="output"
              stroke="#1976d2"
              strokeWidth={2}
              name="Output Voltage"
              dot={false}
            />
            {chartData.some(d => d.input !== null) && (
              <Line
                type="monotone"
                dataKey="input"
                stroke="#ff9800"
                strokeWidth={2}
                name="Input Voltage"
                dot={false}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </Paper>

      {/* Current Waveform */}
      {chartData.some(d => d.current !== null) && (
        <Paper elevation={1} sx={{ p: 2, mb: 2 }}>
          <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
            Current Waveform
          </Typography>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="time"
                label={{ value: 'Time (s)', position: 'insideBottomRight', offset: -5 }}
              />
              <YAxis
                label={{ value: 'Current (mA)', angle: -90, position: 'insideLeft' }}
              />
              <Tooltip />
              <Legend />
              <Line
                type="monotone"
                dataKey="current"
                stroke="#4caf50"
                strokeWidth={2}
                name="Current"
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </Paper>
      )}

      {/* Analysis Type */}
      {results.analysis_type && (
        <Alert severity="info" sx={{ mt: 2 }}>
          Analysis Type: <strong>{results.analysis_type}</strong> |
          Simulation Time: <strong>{results.simulation_time}s</strong>
        </Alert>
      )}
    </Box>
  );
}
