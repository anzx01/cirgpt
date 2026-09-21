"use client";

import React, { useState } from 'react';
import {
  Box,
  Typography,
  Button,
  Alert,
  CircularProgress,
  Chip,
  Stack,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
} from '@mui/material';
import BoltIcon from '@mui/icons-material/Bolt';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import { API_BASE_URL } from '../config.mjs';
import { formatUserError } from '../lib/errorUtils';

const TYPE_LABELS = {
  motor: '电机/水泵',
  pump: '水泵',
  relay: '继电器',
  buzzer: '蜂鸣器',
  speaker: '扬声器',
  solenoid: '电磁阀',
  fan: '风扇',
  led: '指示灯',
};

function fmtA(amps) {
  const a = Math.abs(amps || 0);
  if (a >= 0.1) return `${a.toFixed(2)} A`;
  if (a >= 0.001) return `${(a * 1000).toFixed(1)} mA`;
  return `${(a * 1e6).toFixed(0)} µA`;
}

function fmtV(volts) {
  const v = Math.abs(volts || 0);
  if (v >= 10) return v.toFixed(1);
  return v.toFixed(2);
}

export default function PowerOnTest({ designId, hasIr }) {
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const runTest = async () => {
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const response = await fetch(`${API_BASE_URL}/circuit/${designId}/poweron`, {
        method: 'POST',
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail.detail || `请求失败 (${response.status})`);
      }
      setResult(await response.json());
    } catch (e) {
      setError(formatUserError ? formatUserError(e) : String(e));
    } finally {
      setRunning(false);
    }
  };

  // Verdict classes: 正确切换 (DC sweep) and 周期动作 (transient recheck of
  // timer-driven actuators) are successes; 无法判定 / 短暂动作 / 未参与 mark
  // actuators the DC scan cannot assess (driver excluded from the deck) —
  // neutral, not a drive-chain failure; anything else is a real warning.
  const isSuccess = (a) => /正确切换|周期动作/.test(a.response);
  const isNeutral = (a) => /无法判定|短暂动作|未参与/.test(a.response);
  const allOk = result?.actuator_response?.every?.((a) => isSuccess(a) || isNeutral(a));
  const anyNeutral = result?.actuator_response?.some?.(isNeutral);

  return (
    <Box sx={{ px: 3 }}>
      <Stack direction="row" alignItems="center" spacing={2} sx={{ mb: 2 }}>
        <BoltIcon color="primary" />
        <Typography variant="h6" fontWeight="bold" sx={{ flex: 1 }}>
          通电测试（DC 工况扫描）
        </Typography>
        <Button
          variant="contained"
          color="primary"
          startIcon={running ? <CircularProgress size={18} color="inherit" /> : <PlayArrowIcon />}
          onClick={runTest}
          disabled={running || !hasIr}
        >
          {running ? '正在通电…' : '⚡ 通电测试'}
        </Button>
      </Stack>

      {!hasIr && (
        <Alert severity="info">该设计还没有电路数据（CircuitIR），请先生成设计。</Alert>
      )}

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>
      )}

      {result && (
        <>
          <Alert severity={allOk ? (anyNeutral ? 'info' : 'success') : 'warning'} sx={{ mb: 2 }}>
            <strong>{result.tool}</strong> 上电完成，共 {result.scenarios.length} 个工况。
            {result.actuator_response.length === 0
              ? ' 未检测到执行器（电机/LED 等）。'
              : allOk
                ? (anyNeutral
                    ? ' 可判定的执行器均正常动作，其余无法自动判定（见明细）。'
                    : ' 所有执行器均正常动作 ✓')
                : ' 部分执行器未按预期切换，请看下方明细。'}
          </Alert>

          {result.transient?.performed && (
            <Alert severity="info" sx={{ mb: 2 }}>
              已自动补跑上电瞬态仿真（窗口 {Math.round(result.transient.tstop_ms)} ms）：
              {Object.entries(result.transient.actuators).map(([ref, s]) => (
                <span key={ref}> {ref} 导通占比 {(s.on_fraction * 100).toFixed(0)}%，翻转 {s.transitions} 次；</span>
              ))}
            </Alert>
          )}

          {result.actuator_response.length > 0 && (
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mb: 2 }}>
              {result.actuator_response.map((a) => (
                <Chip
                  key={a.ref}
                  size="small"
                  color={isSuccess(a) ? 'success' : (isNeutral(a) ? 'default' : 'warning')}
                  variant="outlined"
                  label={`${a.ref}（${TYPE_LABELS[a.type] || a.type}）：${a.response}`}
                />
              ))}
            </Stack>
          )}

          <TableContainer component={Paper} elevation={0} sx={{ border: '1px solid', borderColor: 'divider', mb: 3 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell><strong>输入工况</strong></TableCell>
                  {(result.scenarios[0]?.node_voltages
                    ? Object.keys(result.scenarios[0].node_voltages)
                    : []
                  ).map((node) => (
                    <TableCell key={node} align="right">
                      <Tooltip title="直流工作点（节点电压）">
                        <span><strong>V({node})</strong></span>
                      </Tooltip>
                    </TableCell>
                  ))}
                  {(result.scenarios[0]?.actuators || []).map((a) => (
                    <TableCell key={a.ref} align="right">
                      <Tooltip title={`流过 ${a.ref} 的电流`}>
                        <span><strong>{a.ref} 电流</strong></span>
                      </Tooltip>
                    </TableCell>
                  ))}
                  <TableCell><strong>结论</strong></TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {result.scenarios.map((sc, i) => (
                  <TableRow key={i} hover>
                    <TableCell component="th" scope="row">{sc.label}</TableCell>
                    {Object.values(sc.node_voltages || {}).map((v, j) => (
                      <TableCell key={j} align="right" sx={{ fontFamily: 'monospace' }}>
                        {fmtV(v)} V
                      </TableCell>
                    ))}
                    {(sc.actuators || []).map((a, j) => (
                      <TableCell
                        key={j}
                        align="right"
                        sx={{
                          fontFamily: 'monospace',
                          color: a.on ? 'success.main' : 'text.disabled',
                          fontWeight: a.on ? 'bold' : 'normal',
                        }}
                      >
                        {fmtA(a.current_a)}
                      </TableCell>
                    ))}
                    <TableCell>{sc.verdict}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>

          {result.assumptions?.length > 0 && (
            <Paper elevation={0} sx={{ p: 2, border: '1px solid', borderColor: 'divider', mb: 2 }}>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                建模假设
              </Typography>
              <Stack spacing={0.5}>
                {result.assumptions.map((a, i) => (
                  <Typography key={i} variant="body2" color="text.secondary">• {a}</Typography>
                ))}
              </Stack>
            </Paper>
          )}

          {result.skipped?.length > 0 && (
            <Typography variant="caption" color="text.secondary">
              未参与仿真：{result.skipped.join('；')}
            </Typography>
          )}
        </>
      )}
    </Box>
  );
}
