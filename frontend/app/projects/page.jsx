"use client";

import React, { useEffect, useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import {
  Alert,
  Box,
  Button,
  Chip,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  IconButton,
  InputAdornment,
  LinearProgress,
  MenuItem,
  Paper,
  Snackbar,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  Tooltip,
  Typography
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import RefreshIcon from '@mui/icons-material/Refresh';
import AddIcon from '@mui/icons-material/Add';
import VisibilityIcon from '@mui/icons-material/Visibility';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import { API_BASE_URL } from '../../config.mjs';
import { handleApiCall } from '../../lib/errorUtils';

const STATUS_META = {
  pending: { label: '待开始', color: 'default' },
  processing: { label: '生成中', color: 'info' },
  completed: { label: '已完成', color: 'success' },
  failed: { label: '失败', color: 'error' }
};

// 后端存的是无时区的 UTC 时间，补上 Z 再格式化为本地时间
function formatDateTime(iso) {
  if (!iso) return '-';
  const normalized = /[zZ]|[+\-]\d{2}:?\d{2}$/.test(iso) ? iso : `${iso}Z`;
  const d = new Date(normalized);
  return Number.isNaN(d.getTime()) ? '-' : d.toLocaleString();
}

function firstLine(text, maxLen = 40) {
  if (!text) return '';
  const line = text.trim().split('\n')[0];
  return line.length > maxLen ? `${line.slice(0, maxLen)}…` : line;
}

export default function ProjectsPage() {
  const router = useRouter();

  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);

  const [renaming, setRenaming] = useState(null); // 进行重命名的项目
  const [renameValue, setRenameValue] = useState('');
  const [renameError, setRenameError] = useState(null);
  const [renamingBusy, setRenamingBusy] = useState(false);

  const [deleting, setDeleting] = useState(null); // 待删除确认的项目
  const [deletingBusy, setDeletingBusy] = useState(false);

  const [snackbar, setSnackbar] = useState(null);

  const fetchProjects = async (silent = false) => {
    if (!silent) setLoading(true);
    setError(null);
    const result = await handleApiCall(
      () => fetch(`${API_BASE_URL}/circuit/?limit=1000`),
      '获取项目列表'
    );
    if (!result.success) {
      setError(result.error);
      setLoading(false);
      return;
    }
    setProjects(result.data || []);
    setLoading(false);
  };

  useEffect(() => {
    fetchProjects();
  }, []);

  // 生成中的项目自动刷新进度
  useEffect(() => {
    const hasProcessing = projects.some((p) => p.status === 'processing' || p.status === 'pending');
    if (!hasProcessing) return undefined;
    const timer = setInterval(() => fetchProjects(true), 5000);
    return () => clearInterval(timer);
  }, [projects]);

  const filtered = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    return projects.filter((p) => {
      if (statusFilter !== 'all' && p.status !== statusFilter) return false;
      if (!keyword) return true;
      const haystack = `${p.name || ''}\n${p.description || ''}`.toLowerCase();
      return haystack.includes(keyword);
    });
  }, [projects, search, statusFilter]);

  const paged = useMemo(
    () => filtered.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage),
    [filtered, page, rowsPerPage]
  );

  const handleRenameOpen = (project) => {
    setRenaming(project);
    setRenameValue(project.name || firstLine(project.description, 60));
    setRenameError(null);
  };

  const handleRenameSave = async () => {
    const name = renameValue.trim();
    if (!name) {
      setRenameError('项目名称不能为空');
      return;
    }
    if (name.length > 200) {
      setRenameError('名称最多 200 个字符');
      return;
    }
    setRenamingBusy(true);
    const result = await handleApiCall(
      () => fetch(`${API_BASE_URL}/circuit/${renaming.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
      }),
      '重命名项目'
    );
    setRenamingBusy(false);
    if (!result.success) {
      setRenameError(result.error);
      return;
    }
    setProjects((prev) =>
      prev.map((p) => (p.id === renaming.id ? { ...p, name, updated_at: result.data.updated_at } : p))
    );
    setRenaming(null);
    setSnackbar({ severity: 'success', message: '项目已重命名' });
  };

  const handleDeleteConfirm = async () => {
    setDeletingBusy(true);
    const result = await handleApiCall(
      () => fetch(`${API_BASE_URL}/circuit/${deleting.id}`, { method: 'DELETE' }),
      '删除项目'
    );
    setDeletingBusy(false);
    if (!result.success) {
      setSnackbar({ severity: 'error', message: result.error });
      setDeleting(null);
      return;
    }
    setProjects((prev) => prev.filter((p) => p.id !== deleting.id));
    setDeleting(null);
    setSnackbar({ severity: 'success', message: '项目已删除' });
  };

  const statusCount = (status) =>
    status === 'all' ? projects.length : projects.filter((p) => p.status === status).length;

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      <Paper elevation={1} sx={{ p: { xs: 2, md: 3 } }}>
        {/* 标题与操作 */}
        <Stack
          direction={{ xs: 'column', sm: 'row' }}
          justifyContent="space-between"
          alignItems={{ xs: 'flex-start', sm: 'center' }}
          spacing={2}
          sx={{ mb: 3 }}
        >
          <Stack direction="row" spacing={1} alignItems="center">
            <FolderOpenIcon color="primary" />
            <Typography variant="h5" component="h1" fontWeight="bold">
              项目管理
            </Typography>
            <Chip size="small" label={`${filtered.length} / ${projects.length} 个项目`} />
          </Stack>
          <Stack direction="row" spacing={1}>
            <Button
              variant="outlined"
              startIcon={<RefreshIcon />}
              onClick={() => fetchProjects()}
              disabled={loading}
            >
              刷新
            </Button>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => router.push('/design')}
            >
              新建项目
            </Button>
          </Stack>
        </Stack>

        {/* 搜索与状态过滤 */}
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} sx={{ mb: 2 }}>
          <TextField
            size="small"
            placeholder="搜索项目名称或描述…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(0);
            }}
            sx={{ width: { xs: '100%', md: 360 } }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon />
                </InputAdornment>
              )
            }}
          />
          <TextField
            select
            size="small"
            label="状态"
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(0);
            }}
            sx={{ width: 160 }}
          >
            <MenuItem value="all">全部（{statusCount('all')}）</MenuItem>
            {Object.entries(STATUS_META).map(([value, meta]) => (
              <MenuItem key={value} value={value}>
                {meta.label}（{statusCount(value)}）
              </MenuItem>
            ))}
          </TextField>
        </Stack>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {loading ? (
          <LinearProgress />
        ) : (
          <>
            <TableContainer sx={{ overflowX: 'auto' }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>项目名称</TableCell>
                    <TableCell sx={{ display: { xs: 'none', md: 'table-cell' } }}>描述</TableCell>
                    <TableCell>状态</TableCell>
                    <TableCell sx={{ display: { xs: 'none', sm: 'table-cell' } }}>更新时间</TableCell>
                    <TableCell align="right">操作</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {paged.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={5}>
                        <Typography color="text.secondary" align="center" sx={{ py: 4 }}>
                          {projects.length === 0
                            ? '还没有项目，点击右上角「新建项目」开始第一个设计'
                            : '没有符合条件的项目'}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  )}
                  {paged.map((p) => {
                    const meta = STATUS_META[p.status] || { label: p.status, color: 'default' };
                    // 占位草稿：结果不代表原始需求，必须与正常完成区分展示
                    const isGenericDraft =
                      p.status === 'completed' && p.validation_circuit_type === 'generic_circuit';
                    return (
                      <TableRow key={p.id} hover>
                        <TableCell>
                          <Box
                            sx={{ cursor: 'pointer', maxWidth: 280 }}
                            onClick={() => router.push(`/design/${p.id}`)}
                          >
                            <Typography
                              variant="body1"
                              fontWeight="bold"
                              sx={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                            >
                              {p.name || firstLine(p.description)}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              #{p.id}
                            </Typography>
                          </Box>
                        </TableCell>
                        <TableCell sx={{ display: { xs: 'none', md: 'table-cell' }, maxWidth: 360 }}>
                          <Typography
                            variant="body2"
                            color="text.secondary"
                            sx={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                          >
                            {p.description || '-'}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Stack direction="row" spacing={1} alignItems="center">
                            {isGenericDraft ? (
                              <Tooltip title="规则兜底生成的通用占位草稿，不代表原始需求，详情页有警示">
                                <Chip size="small" color="warning" label="占位草稿" />
                              </Tooltip>
                            ) : (
                              <Chip size="small" color={meta.color} label={meta.label} />
                            )}
                            {p.status === 'processing' && (
                              <Typography variant="caption" color="text.secondary">
                                {p.progress ?? 0}%
                              </Typography>
                            )}
                          </Stack>
                          {p.status === 'failed' && p.error_message && (
                            <Typography
                              variant="caption"
                              color="error"
                              sx={{ display: 'block', maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                              title={p.error_message}
                            >
                              {p.error_message}
                            </Typography>
                          )}
                        </TableCell>
                        <TableCell sx={{ display: { xs: 'none', sm: 'table-cell' }, whiteSpace: 'nowrap' }}>
                          <Typography variant="body2" color="text.secondary">
                            {formatDateTime(p.updated_at)}
                          </Typography>
                        </TableCell>
                        <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
                          <Tooltip title="查看详情">
                            <IconButton size="small" onClick={() => router.push(`/design/${p.id}`)}>
                              <VisibilityIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title="重命名">
                            <IconButton size="small" onClick={() => handleRenameOpen(p)}>
                              <EditIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title="删除">
                            <IconButton size="small" color="error" onClick={() => setDeleting(p)}>
                              <DeleteIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>
            <TablePagination
              component="div"
              count={filtered.length}
              page={page}
              onPageChange={(e, newPage) => setPage(newPage)}
              rowsPerPage={rowsPerPage}
              onRowsPerPageChange={(e) => {
                setRowsPerPage(parseInt(e.target.value, 10));
                setPage(0);
              }}
              rowsPerPageOptions={[10, 20, 50]}
              labelRowsPerPage="每页行数"
              labelDisplayedRows={({ from, to, count }) => `${from}-${to} / 共 ${count} 个`}
            />
          </>
        )}
      </Paper>

      {/* 重命名对话框 */}
      <Dialog open={Boolean(renaming)} onClose={() => setRenaming(null)} maxWidth="sm" fullWidth>
        <DialogTitle>重命名项目</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            fullWidth
            value={renameValue}
            onChange={(e) => setRenameValue(e.target.value)}
            margin="dense"
            label="项目名称"
            error={Boolean(renameError)}
            helperText={renameError || '显示在项目列表和详情页，不影响设计内容'}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleRenameSave();
            }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRenaming(null)} disabled={renamingBusy}>
            取消
          </Button>
          <Button onClick={handleRenameSave} variant="contained" disabled={renamingBusy}>
            {renamingBusy ? '保存中…' : '保存'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* 删除确认对话框 */}
      <Dialog open={Boolean(deleting)} onClose={() => setDeleting(null)} maxWidth="sm" fullWidth>
        <DialogTitle>删除项目</DialogTitle>
        <DialogContent>
          <DialogContentText>
            确定要删除项目「{deleting?.name || firstLine(deleting?.description)}」(#{deleting?.id}) 吗？
            <br />
            原理图、仿真结果、PCB、BOM 等所有数据将一并删除，且无法恢复。
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleting(null)} disabled={deletingBusy}>
            取消
          </Button>
          <Button onClick={handleDeleteConfirm} color="error" variant="contained" disabled={deletingBusy}>
            {deletingBusy ? '删除中…' : '删除'}
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={Boolean(snackbar)}
        autoHideDuration={3000}
        onClose={() => setSnackbar(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert severity={snackbar?.severity} onClose={() => setSnackbar(null)}>
          {snackbar?.message}
        </Alert>
      </Snackbar>
    </Container>
  );
}
