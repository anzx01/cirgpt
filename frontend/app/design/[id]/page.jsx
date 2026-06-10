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
  CircularProgress,
  Stack,
  Divider
} from '@mui/material';
import {
  Description as DescriptionIcon,
  ShowChart as SimulationIcon,
  ViewInAr as PcbIcon,
  Checklist as BomIcon,
  Home as HomeIcon,
  FactCheck as ValidationIcon,
  Download as DownloadIcon
} from '@mui/icons-material';
import SchematicViewer from '../../../components/SchematicViewer';
import SimulationViewer from '../../../components/SimulationViewer';
import PcbViewer from '../../../components/PcbViewer';
import BomViewer from '../../../components/BomViewer';
import { API_BASE_URL, WEBSOCKET_URL } from '../../../config.mjs';
import { HybridPollingManager } from '../../../lib/pollingUtils';
import { formatUserError } from '../../../lib/errorUtils';

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
    message: '初始化中...',
    progress: 0,
    status: 'pending'
  });
  const [connectionMode, setConnectionMode] = useState('connecting'); // 'websocket' | 'polling' | 'connecting'
  const [pollingManager, setPollingManager] = useState(null);

  // 获取设计数据
  const fetchDesign = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/circuit/${designId}`);

      if (!response.ok) {
        throw new Error('无法获取设计数据，请检查设计ID是否正确');
      }

      const data = await response.json();
      setDesign(data);
      setLoading(false);

      // 更新进度
      if (data.status === 'completed') {
        setProgress({
          message: '设计生成完成！',
          progress: data.progress ?? 100,
          status: 'completed'
        });
        return true; // 停止轮询
      } else if (data.status === 'failed') {
        setProgress({
          message: `错误：${data.error_message || '生成失败'}`,
          progress: data.progress ?? 0,
          status: 'failed'
        });
        setError(data.error_message);
        return true; // 停止轮询
      } else if (data.status === 'processing') {
        setProgress({
          message: data.current_step || '处理中...',
          progress: data.progress ?? 50,
          status: 'processing'
        });
        return false; // 继续轮询
      } else if (data.status === 'pending') {
        setProgress({
          message: data.current_step || '等待开始...',
          progress: data.progress ?? 10,
          status: 'pending'
        });
        return false; // 继续轮询
      }
      return false;
    } catch (err) {
      console.error('获取设计数据失败:', err);
      const errorMessage = formatUserError('获取设计数据', err);
      setError(errorMessage);
      setLoading(false);
      return true; // 停止轮询
    }
  };

  // 初始化混合轮询/WebSocket管理器
  useEffect(() => {
    let manager = null;
    let wsConnected = false;

    const initManager = async () => {
      // 尝试动态导入 socket.io-client
      try {
        const { io } = await import('socket.io-client');

        // WebSocket配置
        const socket = io(WEBSOCKET_URL, {
          path: '/socket.io',
          transports: ['websocket', 'polling']
        });

        socket.on('connect', () => {
          console.log('WebSocket已连接');
          setConnectionMode('websocket');
          wsConnected = true;
          socket.emit('subscribe', { design_id: Number(designId) });
        });

        socket.on('design.progress', (event) => {
          setProgress({
            message: event.message,
            progress: event.progress,
            status: 'processing'
          });
          // WebSocket收到更新，同步拉取最新数据
          fetchDesign();
        });

        socket.on('design.completed', () => {
          setProgress({
            message: '设计生成完成！',
            progress: 100,
            status: 'completed'
          });
          fetchDesign();
        });

        socket.on('design.failed', (event) => {
          setProgress({
            message: event.message,
            progress: event.progress ?? 0,
            status: 'failed'
          });
          setError(event.message);
          fetchDesign();
        });

        socket.on('connect_error', () => {
          console.warn('WebSocket连接失败，切换到轮询模式');
          if (!wsConnected) {
            setConnectionMode('polling');
            startPolling();
          }
        });

        // 清理函数
        return () => {
          socket.emit('unsubscribe', { design_id: Number(designId) });
          socket.disconnect();
        };
      } catch (error) {
        console.warn('无法加载WebSocket，使用轮询模式:', error);
        setConnectionMode('polling');
        startPolling();
      }
    };

    // 启动轮询（降级方案）
    const startPolling = () => {
      manager = new (require('../../../lib/pollingUtils').PollingManager)({
        interval: 2000, // 2秒轮询一次
        maxDuration: 5 * 60 * 1000, // 5分钟超时
        onPoll: async () => {
          const shouldStop = await fetchDesign();
          return !shouldStop; // 返回true继续，false停止
        },
        onTimeout: () => {
          setError('生成超时（5分钟），请刷新页面查看状态或重新创建设计');
          setProgress({
            message: '生成超时',
            progress: 0,
            status: 'failed'
          });
        },
        onError: (error) => {
          console.error('轮询错误:', error);
        }
      });

      manager.start();
      setPollingManager(manager);
    };

    // 初始化
    const cleanup = initManager();

    // 清理
    return () => {
      if (cleanup && typeof cleanup.then === 'function') {
        cleanup.then(fn => fn && fn());
      }
      if (manager) {
        manager.stop();
      }
    };
  }, [designId]);

  const handleTabChange = (event, newValue) => {
    setTabValue(newValue);
  };

  const handleArtifactDownload = (artifactId) => {
    window.open(`${API_BASE_URL}/circuit/${designId}/artifacts/${artifactId}`, '_blank', 'noopener,noreferrer');
  };

  if (loading) {
    return (
      <Container maxWidth="lg" sx={{ py: 8 }}>
        <Box sx={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', minHeight: 400, gap: 2 }}>
          <CircularProgress size={60} />
          <Typography variant="body1" color="text.secondary">
            正在加载设计数据...
          </Typography>
        </Box>
      </Container>
    );
  }

  if (error && progress.status === 'failed') {
    return (
      <Container maxWidth="lg" sx={{ py: 8 }}>
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
        <Stack direction="row" spacing={2}>
          <Button
            variant="outlined"
            onClick={() => router.push('/')}
          >
            返回首页
          </Button>
          <Button
            variant="contained"
            onClick={() => router.push('/design')}
          >
            创建新设计
          </Button>
        </Stack>
      </Container>
    );
  }

  const isProcessing = progress.status === 'processing' || progress.status === 'pending';

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      {/* 连接模式指示器 */}
      {process.env.NODE_ENV === 'development' && (
        <Box sx={{ mb: 2, display: 'flex', justifyContent: 'flex-end' }}>
          <Chip
            label={`连接模式: ${connectionMode === 'websocket' ? 'WebSocket' : connectionMode === 'polling' ? '轮询' : '连接中'}`}
            size="small"
            color={connectionMode === 'websocket' ? 'success' : 'default'}
          />
        </Box>
      )}

      {/* Header */}
      <Paper elevation={2} sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2, flexWrap: 'wrap', gap: 2 }}>
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Typography variant="h4" fontWeight="bold" gutterBottom>
              电路设计 #{designId}
            </Typography>
            <Typography variant="body1" color="text.secondary" paragraph sx={{ wordBreak: 'break-word' }}>
              {design?.description}
            </Typography>
          </Box>
          <Button
            variant="outlined"
            startIcon={<HomeIcon />}
            onClick={() => router.push('/')}
            sx={{ flexShrink: 0 }}
          >
            返回首页
          </Button>
        </Box>

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
            {pollingManager && (
              <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                已用时间: {Math.round(pollingManager.getElapsedTime() / 1000)}秒 / 超时限制: {Math.round(pollingManager.maxDuration / 1000)}秒
              </Typography>
            )}
          </Box>
        )}

        {!isProcessing && progress.status === 'completed' && (
          <Alert severity="success" sx={{ mt: 2 }}>
            设计生成成功完成！
          </Alert>
        )}
      </Paper>

      {/* Results Tabs */}
      <Paper elevation={2} sx={{ mb: 3 }}>
        <Tabs
          value={tabValue}
          onChange={handleTabChange}
          variant="scrollable"
          scrollButtons="auto"
          sx={{ borderBottom: 1, borderColor: 'divider' }}
        >
          <Tab
            icon={<DescriptionIcon />}
            label="原理图"
            disabled={isProcessing}
          />
          <Tab
            icon={<SimulationIcon />}
            label="仿真"
            disabled={isProcessing || !design?.simulation_results}
          />
          <Tab
            icon={<PcbIcon />}
            label="PCB布局"
            disabled={isProcessing || !design?.pcb_layout}
          />
          <Tab
            icon={<BomIcon />}
            label="物料清单"
            disabled={isProcessing || !design?.bom}
          />
          <Tab
            icon={<ValidationIcon />}
            label="验证"
            disabled={isProcessing || !design?.validation}
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

        <TabPanel value={tabValue} index={4}>
          <Box sx={{ px: 3 }}>
            <Typography variant="h6" fontWeight="bold" gutterBottom>
              验证报告
            </Typography>
            <Alert severity={design?.validation?.status === 'passed' ? 'success' : 'warning'} sx={{ mb: 2 }}>
              状态: <strong>{design?.validation?.status || 'unknown'}</strong>
            </Alert>

            <Grid container spacing={2} sx={{ mb: 3 }}>
              {Object.entries(design?.validation?.checks || {}).map(([key, value]) => (
                <Grid item xs={12} md={6} key={key}>
                  <Paper elevation={0} sx={{ p: 2, border: '1px solid', borderColor: 'divider' }}>
                    <Typography variant="caption" color="text.secondary">
                      {key}
                    </Typography>
                    <Typography variant="body1">{String(value)}</Typography>
                  </Paper>
                </Grid>
              ))}
            </Grid>

            {design?.validation?.warnings?.length > 0 && (
              <Alert severity="warning" sx={{ mb: 3 }}>
                <Stack spacing={1}>
                  {design.validation.warnings.map((warning, index) => (
                    <Typography variant="body2" key={index}>{warning}</Typography>
                  ))}
                </Stack>
              </Alert>
            )}

            <Divider sx={{ my: 3 }} />

            <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
              下载产物
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              {Object.entries(design?.artifacts || {}).map(([artifactId, artifact]) => (
                <Button
                  key={artifactId}
                  variant="outlined"
                  startIcon={<DownloadIcon />}
                  onClick={() => handleArtifactDownload(artifactId)}
                >
                  {artifact.filename || artifactId}
                </Button>
              ))}
            </Box>
          </Box>
        </TabPanel>
      </Paper>

      {/* Actions */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          <Button
            variant="outlined"
            startIcon={<HomeIcon />}
            onClick={() => router.push('/')}
          >
            返回首页
          </Button>
          <Button
            variant="contained"
            onClick={() => router.push('/design')}
          >
            创建新设计
          </Button>
        </Box>
        {!isProcessing && (
          <Chip
            label={`预估成本: $${design?.estimated_cost?.toFixed(2) || '0.00'}`}
            color="success"
            size="medium"
          />
        )}
      </Box>
    </Container>
  );
}
