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

// 数据降采样，避免大数据量导致的性能问题
function downsampleData(data, maxPoints = 1000) {
  if (!data || data.length <= maxPoints) {
    return data;
  }

  const step = Math.ceil(data.length / maxPoints);
  return data.filter((_, index) => index % step === 0);
}

export default function SimulationViewer({ results }) {
  if (!results) {
    return (
      <Box sx={{ p: 4, textAlign: 'center' }}>
        <Alert severity="info">
          仿真结果尚未生成，请等待设计生成完成。
        </Alert>
      </Box>
    );
  }

  const { time, voltages, currents, summary } = results;

  // Prepare chart data with downsampling
  const chartData = useMemo(() => {
    if (!time || !voltages) {
      return [];
    }

    const voltageData = voltages.output || voltages.Vout || [];
    const inputData = voltages.input || voltages.Vin || [];
    const currentData = currents?.total || [];

    // 检查数据是否为空
    if (voltageData.length === 0) {
      return [];
    }

    const rawData = time.map((t, i) => ({
      time: Number(t.toFixed(6)),
      output: voltageData[i] !== undefined ? Number((voltageData[i] || 0).toFixed(3)) : null,
      input: inputData[i] !== undefined ? Number((inputData[i] || 0).toFixed(3)) : null,
      current: currentData[i] !== undefined ? Number((currentData[i] * 1000).toFixed(3)) : null // Convert to mA
    })).filter(point => point.time >= 0 && point.output !== null);

    // 降采样以提高性能
    return downsampleData(rawData, 1000);
  }, [time, voltages, currents]);

  // Calculate statistics
  const stats = useMemo(() => {
    if (!chartData || chartData.length === 0) return null;

    const outputVoltages = chartData.map(d => d.output).filter(v => v !== null);
    if (outputVoltages.length === 0) return null;

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

  // 数据为空的情况
  if (!chartData || chartData.length === 0) {
    return (
      <Box sx={{ p: 4 }}>
        <Alert severity="warning">
          仿真数据为空或格式不正确，无法显示波形图。请检查电路设计或重新生成。
        </Alert>
      </Box>
    );
  }

  // 检查是否有输入电压和电流数据
  const hasInputVoltage = chartData.some(d => d.input !== null);
  const hasCurrent = chartData.some(d => d.current !== null);

  return (
    <Box>
      {/* Header */}
      <Typography variant="h6" fontWeight="bold" gutterBottom>
        电路仿真结果
      </Typography>

      {chartData.length < (time?.length || 0) && (
        <Alert severity="info" sx={{ mb: 2 }}>
          数据点较多，已自动降采样至 {chartData.length} 个点以提高显示性能
        </Alert>
      )}

      {/* Statistics Cards */}
      {stats && (
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={6} md={2.4}>
            <Card>
              <CardContent>
                <Typography variant="caption" color="text.secondary">
                  最大电压
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
                  最小电压
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
                  平均电压
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
                  峰峰值
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
                  频率
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
          电压波形
        </Typography>
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="time"
              label={{ value: '时间 (s)', position: 'insideBottomRight', offset: -5 }}
            />
            <YAxis
              label={{ value: '电压 (V)', angle: -90, position: 'insideLeft' }}
            />
            <Tooltip />
            <Legend />
            <Line
              type="monotone"
              dataKey="output"
              stroke="#1976d2"
              strokeWidth={2}
              name="输出电压"
              dot={false}
              connectNulls
            />
            {hasInputVoltage && (
              <Line
                type="monotone"
                dataKey="input"
                stroke="#ff9800"
                strokeWidth={2}
                name="输入电压"
                dot={false}
                connectNulls
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </Paper>

      {/* Current Waveform */}
      {hasCurrent && (
        <Paper elevation={1} sx={{ p: 2, mb: 2 }}>
          <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
            电流波形
          </Typography>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="time"
                label={{ value: '时间 (s)', position: 'insideBottomRight', offset: -5 }}
              />
              <YAxis
                label={{ value: '电流 (mA)', angle: -90, position: 'insideLeft' }}
              />
              <Tooltip />
              <Legend />
              <Line
                type="monotone"
                dataKey="current"
                stroke="#4caf50"
                strokeWidth={2}
                name="电流"
                dot={false}
                connectNulls
              />
            </LineChart>
          </ResponsiveContainer>
        </Paper>
      )}

      {/* Analysis Type */}
      {results.analysis_type && (
        <Alert severity="info" sx={{ mt: 2 }}>
          分析类型: <strong>{results.analysis_type}</strong>
          {results.simulation_time && (
            <> | 仿真时间: <strong>{results.simulation_time}s</strong></>
          )}
        </Alert>
      )}
    </Box>
  );
}
