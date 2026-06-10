"use client";

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Container,
  Grid,
  MenuItem,
  Paper,
  Select,
  Stack,
  TextField,
  Typography
} from '@mui/material';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import SendIcon from '@mui/icons-material/Send';
import { API_BASE_URL } from '../config.mjs';
import { handleApiCall, validateCircuitDescription, formatUserError } from '../lib/errorUtils';

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

  // 键盘快捷键支持 (Ctrl+Enter 提交)
  useEffect(() => {
    const handleKeyPress = (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
        event.preventDefault();
        if (!isSubmitting && description.trim()) {
          handleSubmit(new Event('submit'));
        }
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [description, isSubmitting]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError(null);

    // 输入验证
    const validation = validateCircuitDescription(description);
    if (!validation.valid) {
      setError(validation.error);
      return;
    }

    const trimmed = description.trim();
    setIsSubmitting(true);

    try {
      // 创建设计
      const createResult = await handleApiCall(
        () => fetch(`${API_BASE_URL}/circuit/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ description: trimmed })
        }),
        '创建设计'
      );

      if (!createResult.success) {
        throw new Error(createResult.error);
      }

      const design = createResult.data;

      // 启动生成
      const generateResult = await handleApiCall(
        () => fetch(`${API_BASE_URL}/circuit/${design.id}/generate`, {
          method: 'POST'
        }),
        '启动生成'
      );

      if (!generateResult.success) {
        throw new Error(generateResult.error);
      }

      // 跳转到结果页面
      router.push(`/design/${design.id}`);
    } catch (err) {
      const errorMessage = formatUserError('提交设计', err, {
        customSolution: '请检查您的输入，确保描述清晰且包含必要的参数（如电压、频率等）'
      });
      setError(errorMessage);
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
                    label="电路设计需求"
                    placeholder="描述您想设计的电路，包括功能、参数、供电方式等..."
                    value={description}
                    onChange={(event) => setDescription(event.target.value)}
                    disabled={isSubmitting}
                    helperText="至少10个字符，最多1000个字符"
                  />

                  {/* 桌面端：Chip按钮 */}
                  <Box sx={{ display: { xs: 'none', md: 'flex' }, flexWrap: 'wrap', gap: 1 }}>
                    {examplePrompts.map((prompt, idx) => (
                      <Chip
                        key={prompt}
                        label={`示例 ${idx + 1}`}
                        onClick={() => setDescription(prompt)}
                        disabled={isSubmitting}
                        variant="outlined"
                        size="small"
                        sx={{
                          cursor: 'pointer',
                          '&:hover': {
                            backgroundColor: 'primary.light',
                            color: 'white'
                          }
                        }}
                        title={prompt}
                      />
                    ))}
                  </Box>

                  {/* 移动端：下拉选择 */}
                  <Box sx={{ display: { xs: 'block', md: 'none' } }}>
                    <Select
                      fullWidth
                      value=""
                      onChange={(e) => setDescription(e.target.value)}
                      displayEmpty
                      disabled={isSubmitting}
                      size="small"
                    >
                      <MenuItem value="" disabled>选择示例提示词</MenuItem>
                      {examplePrompts.map((prompt, idx) => (
                        <MenuItem key={idx} value={prompt}>{prompt}</MenuItem>
                      ))}
                    </Select>
                  </Box>

                  {error && (
                    <Alert severity="error" onClose={() => setError(null)}>
                      {error}
                    </Alert>
                  )}

                  <Button
                    type="submit"
                    variant="contained"
                    size="large"
                    startIcon={isSubmitting ? <CircularProgress size={18} color="inherit" /> : <SendIcon />}
                    disabled={isSubmitting || !description.trim()}
                    sx={{ alignSelf: { xs: 'stretch', sm: 'flex-start' } }}
                  >
                    {isSubmitting ? '提交中...' : '生成设计'}
                  </Button>

                  <Typography variant="caption" color="text.secondary">
                    💡 提示：按 Ctrl+Enter 快速提交
                  </Typography>
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
                v1 版本为受限的电路类型创建经过验证的草图。PCB输出为实验性预览；在集成KiCad DRC之前，Gerber导出功能已禁用。
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
                  输出产物
                </Typography>
                <Typography variant="body1">
                  电路中间表示(CircuitIR)、SPICE网表、SVG原理图、仿真报告、BOM CSV、验证JSON、实验性KiCad PCB预览。
                </Typography>
              </Box>
            </Stack>
          </Paper>
        </Grid>
      </Grid>
    </Container>
  );
}
