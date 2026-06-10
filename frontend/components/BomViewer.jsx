"use client";

import React, { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Button,
  Alert,
  Grid,
  Card,
  CardContent,
  IconButton,
  Collapse,
  useMediaQuery,
  useTheme
} from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { downloadFile } from '../lib/downloadUtils';

// 移动端元件卡片组件
function ComponentCard({ entry, index }) {
  const [expanded, setExpanded] = useState(false);

  const formatPrice = (price) => {
    return typeof price === 'number' ? `$${price.toFixed(4)}` : price || 'N/A';
  };

  return (
    <Card sx={{ mb: 1 }}>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Box>
            <Typography variant="subtitle1" fontWeight="bold">
              {entry.designator}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {entry.component_type} - {entry.value}
            </Typography>
          </Box>
          <Box sx={{ textAlign: 'right' }}>
            <Typography variant="body2" color="primary" fontWeight="bold">
              x{entry.quantity}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {formatPrice(entry.total_price)}
            </Typography>
          </Box>
        </Box>

        <IconButton
          onClick={() => setExpanded(!expanded)}
          sx={{
            transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 0.3s',
            mt: 1
          }}
          size="small"
        >
          <ExpandMoreIcon />
        </IconButton>

        <Collapse in={expanded}>
          <Box sx={{ mt: 2, pt: 2, borderTop: '1px solid', borderColor: 'divider' }}>
            <Grid container spacing={1}>
              <Grid item xs={6}>
                <Typography variant="caption" color="text.secondary">封装</Typography>
                <Typography variant="body2">{entry.footprint}</Typography>
              </Grid>
              <Grid item xs={6}>
                <Typography variant="caption" color="text.secondary">单价</Typography>
                <Typography variant="body2">{formatPrice(entry.unit_price)}</Typography>
              </Grid>
              <Grid item xs={6}>
                <Typography variant="caption" color="text.secondary">供应商</Typography>
                <Typography variant="body2">{entry.supplier}</Typography>
              </Grid>
              <Grid item xs={6}>
                <Typography variant="caption" color="text.secondary">料号</Typography>
                <Typography
                  variant="body2"
                  sx={{
                    fontFamily: 'monospace',
                    fontSize: '0.7rem',
                    bgcolor: 'grey.100',
                    px: 0.5,
                    borderRadius: 0.5
                  }}
                >
                  {entry.part_number}
                </Typography>
              </Grid>
            </Grid>
          </Box>
        </Collapse>
      </CardContent>
    </Card>
  );
}

export default function BomViewer({ bom }) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  if (!bom) {
    return (
      <Box sx={{ p: 4, textAlign: 'center' }}>
        <Alert severity="info">
          物料清单(BOM)尚未生成，请等待设计生成完成。
        </Alert>
      </Box>
    );
  }

  const { entries, summary } = bom;

  const handleDownloadCSV = () => {
    if (!bom.csv) {
      alert('CSV数据不可用');
      return;
    }

    const result = downloadFile(bom.csv, `bom_${bom.design_name || 'circuit'}.csv`, 'text/csv');
    if (!result.success) {
      alert('下载失败，请重试');
    }
  };

  const formatPrice = (price) => {
    return typeof price === 'number' ? `$${price.toFixed(4)}` : price || 'N/A';
  };

  // 检查数据有效性
  const hasValidEntries = entries && Array.isArray(entries) && entries.length > 0;

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2, flexWrap: 'wrap', gap: 2 }}>
        <Typography variant="h6" fontWeight="bold">
          物料清单 (BOM)
        </Typography>
        <Button
          variant="contained"
          startIcon={<DownloadIcon />}
          onClick={handleDownloadCSV}
          disabled={!bom.csv}
          size={isMobile ? 'small' : 'medium'}
        >
          下载CSV
        </Button>
      </Box>

      {/* Summary Cards */}
      {summary && (
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={12} md={4}>
            <Card>
              <CardContent>
                <Typography variant="caption" color="text.secondary">
                  元件总数
                </Typography>
                <Typography variant="h4" color="primary">
                  {summary.total_components || 0}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={4}>
            <Card>
              <CardContent>
                <Typography variant="caption" color="text.secondary">
                  唯一元件数
                </Typography>
                <Typography variant="h4" color="primary">
                  {summary.unique_components || 0}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={4}>
            <Card>
              <CardContent>
                <Typography variant="caption" color="text.secondary">
                  总成本
                </Typography>
                <Typography variant="h4" color="success.main">
                  ${(typeof summary.total_cost === 'number' ? summary.total_cost : 0).toFixed(2)}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {!hasValidEntries && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          物料清单数据为空或格式不正确
        </Alert>
      )}

      {/* BOM Table - 桌面端 */}
      {hasValidEntries && !isMobile && (
        <Paper elevation={1} sx={{ mb: 2 }}>
          <TableContainer sx={{ maxHeight: 440 }}>
            <Table stickyHeader size="small">
              <TableHead>
                <TableRow>
                  <TableCell>位号</TableCell>
                  <TableCell>数量</TableCell>
                  <TableCell>元件类型</TableCell>
                  <TableCell>值</TableCell>
                  <TableCell>封装</TableCell>
                  <TableCell align="right">单价</TableCell>
                  <TableCell align="right">总价</TableCell>
                  <TableCell>供应商</TableCell>
                  <TableCell>料号</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {entries.map((entry, index) => (
                  <TableRow
                    key={index}
                    hover
                    sx={{ '&:last-child td, &:last-child th': { border: 0 } }}
                  >
                    <TableCell component="th" scope="row" sx={{ fontWeight: 'bold' }}>
                      {entry.designator}
                    </TableCell>
                    <TableCell>{entry.quantity}</TableCell>
                    <TableCell>{entry.component_type}</TableCell>
                    <TableCell>{entry.value}</TableCell>
                    <TableCell>{entry.footprint}</TableCell>
                    <TableCell align="right">{formatPrice(entry.unit_price)}</TableCell>
                    <TableCell align="right">{formatPrice(entry.total_price)}</TableCell>
                    <TableCell>{entry.supplier}</TableCell>
                    <TableCell>
                      <Typography
                        variant="body2"
                        sx={{
                          fontFamily: 'monospace',
                          fontSize: '0.75rem',
                          bgcolor: 'grey.100',
                          px: 1,
                          py: 0.5,
                          borderRadius: 0.5,
                          display: 'inline-block'
                        }}
                      >
                        {entry.part_number}
                      </Typography>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      )}

      {/* BOM Cards - 移动端 */}
      {hasValidEntries && isMobile && (
        <Box sx={{ mb: 2 }}>
          {entries.map((entry, index) => (
            <ComponentCard key={index} entry={entry} index={index} />
          ))}
        </Box>
      )}

      {/* Cost Breakdown */}
      {hasValidEntries && (
        <Paper elevation={1} sx={{ p: 2 }}>
          <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
            按元件类型的成本分解
          </Typography>
          <Grid container spacing={1}>
            {Object.entries(
              entries.reduce((acc, entry) => {
                const type = entry.component_type;
                if (!acc[type]) {
                  acc[type] = { count: 0, cost: 0 };
                }
                acc[type].count += entry.quantity || 0;
                acc[type].cost += (typeof entry.total_price === 'number' ? entry.total_price : 0);
                return acc;
              }, {})
            ).map(([type, data]) => (
              <Grid item xs={6} md={3} key={type}>
                <Box sx={{ bgcolor: 'grey.50', p: 1, borderRadius: 1 }}>
                  <Typography variant="caption" color="text.secondary">
                    {type}
                  </Typography>
                  <Typography variant="body2" fontWeight="bold">
                    {data.count} 个 / ${data.cost.toFixed(2)}
                  </Typography>
                </Box>
              </Grid>
            ))}
          </Grid>
        </Paper>
      )}

      {/* Info */}
      <Box sx={{ mt: 2 }}>
        <Alert severity="info">
          <Typography variant="body2">
            💡 <strong>提示:</strong> 下载CSV文件以导入到您的采购系统。价格是基于通用元件的估算，实际价格可能因供应商而异。
          </Typography>
        </Alert>
      </Box>
    </Box>
  );
}
