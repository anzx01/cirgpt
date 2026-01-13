"use client";

import React from 'react';
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
  CardContent
} from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf';

export default function BomViewer({ bom }) {
  if (!bom) {
    return (
      <Box sx={{ p: 4, textAlign: 'center' }}>
        <Alert severity="info">
          No BOM available yet. Please wait for generation to complete.
        </Alert>
      </Box>
    );
  }

  const { entries, summary } = bom;

  const handleDownloadCSV = () => {
    if (!bom.csv) return;

    const blob = new Blob([bom.csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `bom_${bom.design_name || 'circuit'}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const formatPrice = (price) => {
    return typeof price === 'number' ? `$${price.toFixed(4)}` : price;
  };

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6" fontWeight="bold">
          Bill of Materials
        </Typography>
        <Button
          variant="contained"
          startIcon={<DownloadIcon />}
          onClick={handleDownloadCSV}
          disabled={!bom.csv}
        >
          Download CSV
        </Button>
      </Box>

      {/* Summary Cards */}
      {summary && (
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={12} md={4}>
            <Card>
              <CardContent>
                <Typography variant="caption" color="text.secondary">
                  Total Components
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
                  Unique Components
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
                  Total Cost
                </Typography>
                <Typography variant="h4" color="success.main">
                  ${summary.total_cost?.toFixed(2) || '0.00'}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* BOM Table */}
      <Paper elevation={1} sx={{ mb: 2 }}>
        <TableContainer sx={{ maxHeight: 440 }}>
          <Table stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell>Designator</TableCell>
                <TableCell>Quantity</TableCell>
                <TableCell>Component Type</TableCell>
                <TableCell>Value</TableCell>
                <TableCell>Footprint</TableCell>
                <TableCell align="right">Unit Price</TableCell>
                <TableCell align="right">Total Price</TableCell>
                <TableCell>Supplier</TableCell>
                <TableCell>Part Number</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {entries && entries.length > 0 ? (
                entries.map((entry, index) => (
                  <TableRow
                    key={index}
                    hover
                    sx={{ '&:last-child td, &:last-child th': { border: 0 } }}
                  >
                    <TableCell component="th" scope="row">
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
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={9} align="center">
                    <Typography variant="body2" color="text.secondary">
                      No components found
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>

      {/* Cost Breakdown */}
      {entries && entries.length > 0 && (
        <Paper elevation={1} sx={{ p: 2 }}>
          <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
            Cost Breakdown by Component Type
          </Typography>
          <Grid container spacing={1}>
            {entries.reduce((acc, entry) => {
              const type = entry.component_type;
              if (!acc[type]) {
                acc[type] = { count: 0, cost: 0 };
              }
              acc[type].count += entry.quantity;
              acc[type].cost += entry.total_price;
              return acc;
            }, {})}
            {Object.entries(
              entries.reduce((acc, entry) => {
                const type = entry.component_type;
                if (!acc[type]) {
                  acc[type] = { count: 0, cost: 0 };
                }
                acc[type].count += entry.quantity;
                acc[type].cost += entry.total_price;
                return acc;
              }, {})
            ).map(([type, data]) => (
              <Grid item xs={6} md={3} key={type}>
                <Box sx={{ bgcolor: 'grey.50', p: 1, borderRadius: 1 }}>
                  <Typography variant="caption" color="text.secondary">
                    {type}
                  </Typography>
                  <Typography variant="body2" fontWeight="bold">
                    {data.count} pcs / ${data.cost.toFixed(2)}
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
            💡 <strong>Tip:</strong> Download the CSV to import into your preferred procurement system.
            Prices are estimates based on generic components. Actual prices may vary by supplier.
          </Typography>
        </Alert>
      </Box>
    </Box>
  );
}
