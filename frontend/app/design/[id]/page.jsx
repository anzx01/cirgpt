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
  Divider,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Tooltip
} from '@mui/material';
import {
  Description as DescriptionIcon,
  ShowChart as SimulationIcon,
  ViewInAr as PcbIcon,
  Checklist as BomIcon,
  Home as HomeIcon,
  FolderOpen as ProjectsIcon,
  FactCheck as ValidationIcon,
  Download as DownloadIcon,
  Visibility as VisibilityIcon,
  Bolt as PowerOnIcon,
  ViewSidebar as ViewSidebarIcon
} from '@mui/icons-material';
import SchematicViewer from '../../../components/SchematicViewer';
import CircuitExplainer from '../../../components/CircuitExplainer';
import CircuitChat from '../../../components/CircuitChat';
import SimulationViewer from '../../../components/SimulationViewer';
import PcbViewer from '../../../components/PcbViewer';
import BomViewer from '../../../components/BomViewer';
import RawDeepseekDialog from '../../../components/RawDeepseekDialog';
import PowerOnTest from '../../../components/PowerOnTest';
import { API_BASE_URL, WEBSOCKET_URL } from '../../../config.mjs';
import { PollingManager } from '../../../lib/pollingUtils';
import { formatUserError } from '../../../lib/errorUtils';

function TabPanel({ children, value, index }) {
  return (
    <div role="tabpanel" hidden={value !== index} style={value === index ? { height: '100%' } : undefined}>
      {value === index && <Box sx={{ py: 1.5, height: '100%', overflowY: 'auto' }}>{children}</Box>}
    </div>
  );
}

// 验证报告展示翻译：后端字段保持英文稳定契约，界面统一中文
const CHECK_LABELS = {
  circuit_ir_supported: 'CircuitIR 支持',
  spice_netlist_generated: 'SPICE 网表',
  schematic_generator: '原理图生成器',
  kicad_schematic_generated: 'KiCad 原理图',
  kicad_erc_status: 'KiCad ERC',
  simulation_status: '电路仿真',
  pcb_status: 'PCB 状态',
  gerber_export: 'Gerber 导出',
};

const CHECK_VALUE_LABELS = {
  true: '是',
  false: '否',
  passed: '通过',
  warning: '有警告',
  failed: '未通过',
  not_run: '未运行',
  unknown: '未知',
  success: '成功',
  degraded: '已降级（含披露限制）',
  experimental_preview_only: '实验性预览（非生产文件）',
  preview: '预览',
  disabled_in_v1: 'v1 未开放',
  'mcp:mcp-kicad-sch-api': 'KiCad MCP 服务（标准库符号）',
  'skidl+kicad-cli': 'SKiDL + KiCad CLI',
};

const VALIDATION_STATUS_LABELS = {
  passed: '通过',
  degraded: '已降级——功能可用但有披露的限制（见下方警告）',
  failed: '失败',
  unknown: '未知',
};

const formatCheckValue = (value) => {
  const raw = String(value);
  return CHECK_VALUE_LABELS[raw] ?? raw;
};

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
  const [rawOpen, setRawOpen] = useState(false);
  const [rawData, setRawData] = useState(null);
  const [rawLoading, setRawLoading] = useState(false);
  const [rawError, setRawError] = useState(null);
  // 原理图专注模式：隐藏右侧解读+chat，原理图横向占满全宽
  const [sidebarHidden, setSidebarHidden] = useState(false);
  useEffect(() => {
    try { setSidebarHidden(window.localStorage.getItem('design-sidebar-hidden') === '1'); } catch { /* private mode */ }
  }, []);
  const toggleSidebar = () => {
    setSidebarHidden((prev) => {
      const next = !prev;
      try { window.localStorage.setItem('design-sidebar-hidden', next ? '1' : '0'); } catch { /* ignore */ }
      return next;
    });
  };

  // 获取设计数据
  const fetchDesign = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/circuit/${designId}`, { cache: 'no-store' });

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
          // 已完成的设计不会再推送事件，连接后主动拉取一次最新状态
          fetchDesign();
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
      manager = new PollingManager({
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

    // 初始化：立即拉取一次当前状态，再建立 WebSocket/轮询通道
    fetchDesign();
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

  const handleOpenRaw = async () => {
    setRawOpen(true);
    if (rawData || rawLoading) {
      return;
    }
    setRawLoading(true);
    setRawError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/circuit/${designId}/raw-deepseek`);
      if (response.status === 404) {
        setRawError('No raw DeepSeek response is available for this design (rule-based parser was used, or the key was not configured).');
        setRawData(null);
        return;
      }
      if (!response.ok) {
        throw new Error(`Failed to load raw response (${response.status})`);
      }
      const data = await response.json();
      setRawData(data);
    } catch (err) {
      setRawError(formatUserError('Load raw DeepSeek response', err));
    } finally {
      setRawLoading(false);
    }
  };

  const handleCloseRaw = () => {
    setRawOpen(false);
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
    <Container maxWidth="xl" sx={{ py: 1, px: { lg: 2 }, height: 'calc(100vh - 64px)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* 一屏工作台模式：隐藏全局页脚与 main 默认内边距（仅本页生效） */}
      <style>{'#app-footer{display:none!important}main{padding:0!important}'}</style>

      {/* 连接模式指示器（仅非 WebSocket 时提示降级） */}
      {process.env.NODE_ENV === 'development' && connectionMode !== 'websocket' && (
        <Chip
          label={`连接模式: ${connectionMode === 'polling' ? '轮询' : '连接中'}`}
          size="small"
          sx={{ alignSelf: 'flex-end', mb: 0.5, flexShrink: 0 }}
        />
      )}

      {/* Header（紧凑单行式） */}
      <Paper elevation={2} sx={{ p: 1.25, mb: 1, flexShrink: 0 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, flexWrap: 'wrap' }}>
          <Typography variant="subtitle1" fontWeight="bold" noWrap sx={{ maxWidth: { md: 300 } }}
            title={design?.name || `电路设计 #${designId}`}>
            {design?.name || `电路设计 #${designId}`}
            <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 0.75 }}>
              #{designId}
            </Typography>
          </Typography>
          <Typography variant="body2" color="text.secondary" noWrap sx={{ flex: 1, minWidth: 100 }}
            title={design?.description}>
            {design?.description}
          </Typography>
          {design?.circuit_ir?.source?.prompt_version && (
            <Chip size="small" variant="outlined" color="primary" label={`prompt: ${design.circuit_ir.source.prompt_version}`} />
          )}
          {Array.isArray(design?.circuit_ir?.subsystems) && design.circuit_ir.subsystems.length > 0 && (
            <Chip size="small" variant="outlined" color="secondary" label={`子系统 ${design.circuit_ir.subsystems.length}`} />
          )}
          {!isProcessing && progress.status === 'completed' && (
            <Chip size="small" color="success" variant="outlined" label="✓ 生成完成" />
          )}
          <Stack direction="row" spacing={0.5} sx={{ flexShrink: 0, alignItems: 'center' }}>
            <Button variant="outlined" size="small" startIcon={<VisibilityIcon />} onClick={handleOpenRaw} disabled={rawLoading}>
              {rawLoading ? '加载中…' : '原始响应'}
            </Button>
            <Button variant="contained" size="small" onClick={() => router.push('/design')}>新设计</Button>
            <Button variant="outlined" size="small" startIcon={<ProjectsIcon />} onClick={() => router.push('/projects')}>项目</Button>
            <Button variant="outlined" size="small" startIcon={<HomeIcon />} onClick={() => router.push('/')}>首页</Button>
            {!isProcessing && (
              <Chip label={`$${design?.estimated_cost?.toFixed(2) || '0.00'}`} color="success" size="small" />
            )}
          </Stack>
        </Box>

        {isProcessing && (
          <Box sx={{ mt: 1 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
              <Typography variant="body2" color="text.secondary">
                {progress.message}
              </Typography>
              <Typography variant="body2" color="primary" fontWeight="bold">
                {progress.progress}%
              </Typography>
            </Box>
            <LinearProgress variant="determinate" value={progress.progress} sx={{ height: 8, borderRadius: 4 }} />
            {pollingManager && (
              <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
                已用 {Math.round(pollingManager.getElapsedTime() / 1000)}s / 上限 {Math.round(pollingManager.maxDuration / 1000)}s
              </Typography>
            )}
          </Box>
        )}

        {!isProcessing && progress.status === 'completed' && (() => {
          const v = design?.validation || {};
          const isGenericDraft = v.circuit_type === 'generic_circuit';
          const unfulfilled = v.unfulfilled_items || [];
          const partial = !isGenericDraft && (unfulfilled.length > 0 || v.requirements_fulfilled === false);
          if (isGenericDraft) {
            return (
              <Alert severity="warning" sx={{ mt: 1, py: 0.5, '& .MuiAlert-message': { minWidth: 0 } }}>
                <Typography variant="body2" fontWeight="bold">该结果是通用占位草稿，并非按你的原始需求实现，请勿直接使用：</Typography>
                <Stack spacing={0}>
                  {(v.warnings || []).slice(0, 3).map((w, i) => (
                    <Typography key={i} variant="caption">• {w}</Typography>
                  ))}
                </Stack>
              </Alert>
            );
          }
          if (partial) {
            return (
              <Alert severity="warning" sx={{ mt: 1, py: 0.5 }}>
                <Typography variant="body2">
                  电路已按描述生成，但有部分内容未能实现——{unfulfilled[0] || '详见「验证」页'}
                </Typography>
              </Alert>
            );
          }
          return null;
        })()}
      </Paper>

      {/* Results Tabs（flex 工作台容器） */}
      <Paper elevation={2} sx={{ mb: 0, flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', minHeight: 44, flexShrink: 0, borderBottom: 1, borderColor: 'divider' }}>
          <Tabs
            value={tabValue}
            onChange={handleTabChange}
            variant="scrollable"
            scrollButtons="auto"
            sx={{
              flex: 1, minHeight: 44,
              '& .MuiTab-root': { minHeight: 44, py: 0.5 },
            }}
          >
            <Tab icon={<DescriptionIcon />} iconPosition="start" label="原理图" disabled={isProcessing} />
            <Tab icon={<SimulationIcon />} iconPosition="start" label="仿真" disabled={isProcessing || !(design?.simulation_results || design?.circuit_ir)} />
            <Tab icon={<PcbIcon />} iconPosition="start" label="PCB布局" disabled={isProcessing || !design?.pcb_layout} />
            <Tab icon={<BomIcon />} iconPosition="start" label="物料清单" disabled={isProcessing || !design?.bom} />
            <Tab icon={<ValidationIcon />} iconPosition="start" label="验证" disabled={isProcessing || !design?.validation} />
            <Tab icon={<PowerOnIcon />} iconPosition="start" label="通电测试" disabled={isProcessing || !design?.circuit_ir} />
          </Tabs>
          <Tooltip title={sidebarHidden ? '显示右侧解读与对话' : '隐藏右侧栏，原理图占满全宽'}>
            <IconButton
              onClick={toggleSidebar}
              size="small"
              sx={{ mr: 1, color: sidebarHidden ? 'primary.main' : 'text.secondary' }}
              aria-label="toggle sidebar"
            >
              <ViewSidebarIcon />
            </IconButton>
          </Tooltip>
        </Box>

        <Box sx={{ flex: 1, minHeight: 0 }}>
          <TabPanel value={tabValue} index={0}>
            <Grid container spacing={1.5} sx={{ height: '100%' }}>
              <Grid item xs={12} lg={sidebarHidden ? 12 : 8} sx={{ height: '100%' }}>
                <SchematicViewer svg={design?.schematic_svg} pages={design?.schematic_pages} fillHeight />
              </Grid>
              {!sidebarHidden && (
                <Grid item xs={12} lg={4} sx={{ height: '100%' }}>
                <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 1.5, minHeight: 0 }}>
                  <CircuitExplainer
                    designId={designId}
                    circuitIr={design?.circuit_ir}
                    initialExplanation={design?.circuit_explanation}
                    fillHeight
                  />
                  <Box sx={{ flex: 1, minHeight: 180 }}>
                    <CircuitChat
                      designId={designId}
                      chatMessages={design?.chat_messages}
                      designStatus={design?.status}
                      onRefresh={() => fetchDesign()}
                      fillHeight
                    />
                  </Box>
                </Box>
              </Grid>
              )}
            </Grid>
          </TabPanel>

        <TabPanel value={tabValue} index={1}>
          <SimulationViewer results={design?.simulation_results} designId={designId} />
        </TabPanel>

        <TabPanel value={tabValue} index={2}>
          <Box sx={{ height: '100%' }}>
            <PcbViewer layout={design?.pcb_layout} image={design?.pcb_image} fillHeight />
          </Box>
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
              状态: <strong>{VALIDATION_STATUS_LABELS[design?.validation?.status] || design?.validation?.status || '未知'}</strong>
            </Alert>

            <Grid container spacing={2} sx={{ mb: 3 }}>
              {Object.entries(design?.validation?.checks || {}).map(([key, value]) => (
                <Grid item xs={12} md={6} key={key}>
                  <Paper elevation={0} sx={{ p: 2, border: '1px solid', borderColor: 'divider' }}>
                    <Typography variant="caption" color="text.secondary">
                      {CHECK_LABELS[key] || key}
                    </Typography>
                    <Typography variant="body1">{formatCheckValue(value)}</Typography>
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

            {design?.validation?.erc?.violations?.length > 0 && (
              <>
                <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
                  KiCad ERC 明细
                </Typography>
                <TableContainer component={Paper} elevation={0} variant="outlined" sx={{ mb: 3 }}>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell width={90}>级别</TableCell>
                        <TableCell width={260}>类型</TableCell>
                        <TableCell>说明</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {design.validation.erc.violations.map((v, i) => (
                        <TableRow key={i}>
                          <TableCell>
                            <Chip
                              size="small"
                              color={v.severity === 'error' ? 'error' : 'warning'}
                              label={v.severity === 'error' ? '错误' : '警告'}
                            />
                          </TableCell>
                          <TableCell>{v.type}</TableCell>
                          <TableCell>{v.description}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </>
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

        <TabPanel value={tabValue} index={5}>
          <PowerOnTest designId={designId} hasIr={!!design?.circuit_ir} />
        </TabPanel>
        </Box>
      </Paper>

      <RawDeepseekDialog
        open={rawOpen}
        onClose={handleCloseRaw}
        raw={rawData}
      />

      {rawError && !rawOpen && (
        <Box sx={{ position: 'fixed', bottom: 24, right: 24, maxWidth: 360, zIndex: 1500 }}>
          <Alert severity="info" onClose={() => setRawError(null)}>
            {rawError}
          </Alert>
        </Box>
      )}
    </Container>
  );
}
