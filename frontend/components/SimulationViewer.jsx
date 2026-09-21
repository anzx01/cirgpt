"use client";

import React, { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Grid,
  Card,
  CardContent,
  Alert,
  Button,
  Stack,
  CircularProgress
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
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
import { API_BASE_URL } from '../config.mjs';
import { formatUserError } from '../lib/errorUtils';

const SERIES_COLORS = [
  '#1976d2', '#ff9800', '#4caf50', '#9c27b0',
  '#f44336', '#00bcd4', '#795548', '#607d8b',
];

// 数据降采样，避免大数据量导致的性能问题
function downsampleData(data, maxPoints = 1000) {
  if (!data || data.length <= maxPoints) {
    return data;
  }

  const step = Math.ceil(data.length / maxPoints);
  return data.filter((_, index) => index % step === 0);
}

export default function SimulationViewer({ results, designId }) {
  const [data, setData] = useState(results);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    setData(results);
    setError(null);
  }, [results]);

  const rerun = async () => {
    setRunning(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/circuit/${designId}/simulate`, {
        method: 'POST',
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail.detail || `请求失败 (${response.status})`);
      }
      const payload = await response.json();
      setData(payload.results || payload);
    } catch (e) {
      setError(formatUserError ? formatUserError(e) : String(e));
    } finally {
      setRunning(false);
    }
  };

  const voltages = data?.voltages || {};
  const currents = data?.currents || {};
  const time = data?.time;

  // node series to plot: output/input aliases first, then named nodes (max 6)
  const nodeKeys = useMemo(() => {
    const keys = Object.keys(voltages).filter(
      (k) => Array.isArray(voltages[k]) && voltages[k].length > 0
    );
    const priority = (k) => (k === 'output' ? 0 : k === 'input' ? 1 : 2);
    return keys.sort((a, b) => priority(a) - priority(b)).slice(0, 6);
  }, [voltages]);

  const chartData = useMemo(() => {
    if (!time || nodeKeys.length === 0) {
      return [];
    }
    const currentData = currents?.total || [];
    const rawData = time.map((t, i) => {
      const point = { time: Number(Number(t).toFixed(6)) };
      for (const k of nodeKeys) {
        const v = voltages[k][i];
        point[k] = v !== undefined ? Number(Number(v || 0).toFixed(3)) : null;
      }
      point.current =
        currentData[i] !== undefined
          ? Number((currentData[i] * 1000).toFixed(3)) // A -> mA
          : null;
      return point;
    }).filter((point) => point.time >= 0 && point[nodeKeys[0]] !== null);
    return downsampleData(rawData, 1000);
  }, [time, nodeKeys, voltages, currents]);

  const stats = useMemo(() => {
    if (chartData.length === 0) return null;
    const outputVoltages = chartData
      .map((d) => (nodeKeys.includes('output') ? d.output : d[nodeKeys[0]]))
      .filter((v) => v !== null && v !== undefined);
    if (outputVoltages.length === 0) return null;

    const vMax = Math.max(...outputVoltages);
    const vMin = Math.min(...outputVoltages);
    const vAvg = outputVoltages.reduce((a, b) => a + b, 0) / outputVoltages.length;

    return {
      vMax: vMax.toFixed(2),
      vMin: vMin.toFixed(2),
      vAvg: vAvg.toFixed(2),
      vPeakToPeak: (vMax - vMin).toFixed(2),
      frequency:
        data?.summary?.estimated_frequency != null
          ? data.summary.estimated_frequency.toFixed(2)
          : 'N/A'
    };
  }, [chartData, nodeKeys, data]);

  const degraded = data?.degraded || chartData.length === 0;
  const hasCurrent = chartData.some((d) => d.current !== null);

  const header = (
    <Stack direction="row" alignItems="center" spacing={2} sx={{ mb: 2 }}>
      <Typography variant="h6" fontWeight="bold" sx={{ flex: 1 }}>
        电路仿真结果
      </Typography>
      {data?.scenario && (
        <Typography variant="caption" color="text.secondary">
          工况：{data.scenario}
        </Typography>
      )}
      {designId && (
        <Button
          variant="contained"
          size="small"
          color="primary"
          startIcon={running ? <CircularProgress size={16} color="inherit" /> : <RefreshIcon />}
          onClick={rerun}
          disabled={running}
        >
          {running ? '仿真中…' : '重新仿真'}
        </Button>
      )}
    </Stack>
  );

  if (!data) {
    return (
      <Box sx={{ p: 4, textAlign: 'center' }}>
        <Alert severity="info">
          仿真结果尚未生成，请等待设计生成完成。
        </Alert>
      </Box>
    );
  }

  if (degraded) {
    return (
      <Box sx={{ px: 3 }}>
        {header}
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        <Alert severity="warning">
          {data?.message || '仿真数据为空或格式不正确。'}
          {designId
            ? ' 连接性网表会用 CircuitIR 工程模型做上电瞬态仿真，点击右上角「重新仿真」生成波形。'
            : ''}
        </Alert>
        {data?.assumptions?.length > 0 && (
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
            建模假设：{data.assumptions.join('；')}
          </Typography>
        )}
      </Box>
    );
  }

  return (
    <Box>
      {header}
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

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

      {/* Voltage Waveform: one line per node (output/input aliases first) */}
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
            {nodeKeys.map((k, i) => (
              <Line
                key={k}
                type="monotone"
                dataKey={k}
                stroke={SERIES_COLORS[i % SERIES_COLORS.length]}
                strokeWidth={k === 'output' || k === 'input' ? 2 : 1.5}
                name={`V(${k})`}
                dot={false}
                connectNulls
              />
            ))}
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
                name="电源电流"
                dot={false}
                connectNulls
              />
            </LineChart>
          </ResponsiveContainer>
        </Paper>
      )}

      {data?.assumptions?.length > 0 && (
        <Typography variant="caption" color="text.secondary">
          建模假设：{data.assumptions.join('；')}
        </Typography>
      )}

      {/* Analysis Type */}
      {data.analysis_type && (
        <Alert severity="info" sx={{ mt: 2 }}>
          分析类型: <strong>{data.analysis_type}</strong>
          {data.simulation_time ? (
            <> | 仿真时间: <strong>{Number(data.simulation_time * 1000).toFixed(1)}ms</strong></>
          ) : null}
        </Alert>
      )}
    </Box>
  );
}
