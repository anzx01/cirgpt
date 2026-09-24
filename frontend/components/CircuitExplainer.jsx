"use client";

import React, { useEffect, useRef, useState } from 'react';
import {
  Box,
  Typography,
  Button,
  Alert,
  CircularProgress,
  Chip,
  Stack,
  Paper,
  Divider,
  Tooltip,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import MemoryIcon from '@mui/icons-material/Memory';
import NotesIcon from '@mui/icons-material/Notes';
import LightbulbIcon from '@mui/icons-material/Lightbulb';
import { API_BASE_URL } from '../config.mjs';
import { formatUserError } from '../lib/errorUtils';

function SectionTitle({ icon, children }) {
  return (
    <Stack direction="row" alignItems="center" spacing={1} sx={{ mt: 2.5, mb: 1 }}>
      {icon}
      <Typography variant="subtitle2" fontWeight="bold">
        {children}
      </Typography>
    </Stack>
  );
}

export default function CircuitExplainer({ designId, circuitIr, initialExplanation }) {
  const [explanation, setExplanation] = useState(initialExplanation || null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  // 设计刚生成完成时 initialExplanation 尚未就绪；只在没有缓存的解释时自动生成一次
  const requestedRef = useRef(Boolean(initialExplanation));
  const aliveRef = useRef(true);

  useEffect(() => {
    aliveRef.current = true;
    return () => { aliveRef.current = false; };
  }, []);

  const load = async (refresh = false) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(
        `${API_BASE_URL}/circuit/${designId}/explain${refresh ? '?refresh=true' : ''}`,
        { method: 'POST' }
      );
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail.detail || `请求失败 (${response.status})`);
      }
      const data = await response.json();
      if (aliveRef.current) setExplanation(data.explanation);
    } catch (e) {
      if (aliveRef.current) setError(formatUserError('生成电路解读', e));
    } finally {
      if (aliveRef.current) setLoading(false);
    }
  };

  // 原理图生成成功后自动加载解释（仅一次；缓存命中由后端直接返回）
  useEffect(() => {
    if (requestedRef.current || !circuitIr) return;
    requestedRef.current = true;
    load(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [circuitIr]);

  if (!circuitIr) {
    return (
      <Paper elevation={0} sx={{ p: 2, border: '1px solid', borderColor: 'divider' }}>
        <Typography variant="body2" color="text.secondary">
          该设计还没有电路数据（CircuitIR），无法解读。
        </Typography>
      </Paper>
    );
  }

  const isRule = explanation?.source === 'rule';

  return (
    <Paper
      elevation={0}
      sx={{
        p: 2.5,
        border: '1px solid',
        borderColor: 'divider',
        height: 'fit-content',
        maxHeight: 'calc(100vh - 140px)',
        overflowY: 'auto',
        position: 'sticky',
        top: 16,
      }}
    >
      <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 0.5 }}>
        <AutoAwesomeIcon color="primary" fontSize="small" />
        <Typography variant="subtitle1" fontWeight="bold" sx={{ flex: 1 }}>
          电路原理解读
        </Typography>
        <Tooltip title={explanation ? '重新生成解读' : '生成解读'}>
          <span>
            <Button
              size="small"
              variant="outlined"
              startIcon={loading
                ? <CircularProgress size={14} color="inherit" />
                : <RefreshIcon />}
              onClick={() => load(true)}
              disabled={loading}
            >
              {loading ? '生成中…' : '重新生成'}
            </Button>
          </span>
        </Tooltip>
      </Stack>

      {explanation && (
        <Chip
          size="small"
          color={isRule ? 'default' : 'primary'}
          variant="outlined"
          label={isRule ? '结构分析（AI 解读不可用时的降级摘要）' : 'AI 解读'}
          sx={{ mb: 1 }}
        />
      )}

      {loading && !explanation && (
        <Stack alignItems="center" spacing={1.5} sx={{ py: 6 }}>
          <CircularProgress size={36} />
          <Typography variant="body2" color="text.secondary">
            正在结合电路结构生成原理解读，约需十几秒…
          </Typography>
        </Stack>
      )}

      {error && (
        <Alert
          severity="error"
          sx={{ mt: 1 }}
          action={
            <Button color="inherit" size="small" onClick={() => load(false)}>
              重试
            </Button>
          }
        >
          {error}
        </Alert>
      )}

      {explanation && (
        <Box>
          {(explanation.warnings || []).map((w, i) => (
            <Alert key={i} severity="warning" sx={{ mt: 1 }}>{w}</Alert>
          ))}

          {explanation.summary && (
            <Typography variant="body2" sx={{ mt: 1.5, lineHeight: 1.7 }}>
              {explanation.summary}
            </Typography>
          )}

          {(explanation.how_it_works || []).length > 0 && (
            <>
              <SectionTitle icon={<LightbulbIcon fontSize="small" color="primary" />}>
                工作原理
              </SectionTitle>
              <Stack spacing={1}>
                {explanation.how_it_works.map((step, i) => (
                  <Stack key={i} direction="row" spacing={1} sx={{ alignItems: 'flex-start' }}>
                    <Chip label={i + 1} size="small" sx={{ flexShrink: 0, minWidth: 24, height: 22 }} />
                    <Typography variant="body2" sx={{ lineHeight: 1.7 }}>{step}</Typography>
                  </Stack>
                ))}
              </Stack>
            </>
          )}

          {(explanation.component_roles || []).length > 0 && (
            <>
              <SectionTitle icon={<MemoryIcon fontSize="small" color="primary" />}>
                器件作用
              </SectionTitle>
              <Stack spacing={1.25} sx={{ maxHeight: 320, overflowY: 'auto', pr: 0.5 }}>
                {explanation.component_roles.map((c) => (
                  <Box key={c.ref}>
                    <Typography variant="body2" component="span" sx={{ fontFamily: 'monospace', fontWeight: 'bold' }}>
                      {c.ref}
                    </Typography>
                    {c.role && (
                      <Typography variant="body2" component="span" color="primary" sx={{ mx: 0.75 }}>
                        {c.role}
                      </Typography>
                    )}
                    {c.purpose && (
                      <Typography variant="body2" color="text.secondary" sx={{ display: 'inline', lineHeight: 1.65 }}>
                        {c.purpose}
                      </Typography>
                    )}
                  </Box>
                ))}
              </Stack>
            </>
          )}

          {(explanation.net_walkthrough || []).length > 0 && (
            <>
              <SectionTitle icon={<AccountTreeIcon fontSize="small" color="primary" />}>
                连接关系
              </SectionTitle>
              <Stack spacing={1}>
                {explanation.net_walkthrough.map((n) => (
                  <Box key={n.net} sx={{ pl: 1, borderLeft: 2, borderColor: 'primary.light' }}>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 'bold' }}>
                      {n.net}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.65 }}>
                      {n.description}
                    </Typography>
                  </Box>
                ))}
              </Stack>
            </>
          )}

          {(explanation.subsystems || []).length > 0 && (
            <>
              <SectionTitle icon={<AccountTreeIcon fontSize="small" color="primary" />}>
                子电路划分
              </SectionTitle>
              <Stack spacing={1}>
                {explanation.subsystems.map((s, i) => (
                  <Box key={i}>
                    <Chip size="small" variant="outlined" label={s.name} sx={{ mr: 0.75 }} />
                    {s.function && (
                      <Typography variant="body2" color="text.secondary" sx={{ display: 'inline', lineHeight: 1.65 }}>
                        {s.function}
                      </Typography>
                    )}
                  </Box>
                ))}
              </Stack>
            </>
          )}

          {(explanation.design_notes || []).length > 0 && (
            <>
              <Divider sx={{ my: 2 }} />
              <SectionTitle icon={<NotesIcon fontSize="small" color="action" />}>
                设计说明
              </SectionTitle>
              <Stack spacing={0.5}>
                {explanation.design_notes.map((note, i) => (
                  <Typography key={i} variant="body2" color="text.secondary">
                    • {note}
                  </Typography>
                ))}
              </Stack>
            </>
          )}

          {explanation.source_detail?.model && (
            <Typography variant="caption" color="text.disabled" sx={{ display: 'block', mt: 2.5 }}>
              解读模型：{explanation.source_detail.model}
            </Typography>
          )}
        </Box>
      )}
    </Paper>
  );
}
