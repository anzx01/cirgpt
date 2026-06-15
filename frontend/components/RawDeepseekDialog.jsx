"use client";

import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Chip,
  Stack,
  Tabs,
  Tab,
  Typography,
  IconButton
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import { useState } from 'react';

function TabPanel({ children, value, index }) {
  return (
    <div role="tabpanel" hidden={value !== index}>
      {value === index && <Box sx={{ pt: 1 }}>{children}</Box>}
    </div>
  );
}

function CodeBlock({ text, maxHeight = 360 }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text || '');
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch (e) {
      // ignore clipboard failure
    }
  };

  return (
    <Box sx={{ position: 'relative' }}>
      <IconButton
        size="small"
        onClick={handleCopy}
        sx={{ position: 'absolute', top: 6, right: 6, zIndex: 1 }}
        title="Copy to clipboard"
      >
        <ContentCopyIcon fontSize="inherit" />
      </IconButton>
      {copied && (
        <Typography
          variant="caption"
          sx={{ position: 'absolute', top: 8, right: 44, color: 'success.main' }}
        >
          Copied
        </Typography>
      )}
      <Box
        component="pre"
        sx={{
          bgcolor: 'grey.900',
          color: 'grey.100',
          p: 1.5,
          borderRadius: 1,
          fontSize: 12,
          fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
          overflow: 'auto',
          maxHeight,
          m: 0,
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word'
        }}
      >
        {text}
      </Box>
    </Box>
  );
}

export default function RawDeepseekDialog({ open, onClose, raw }) {
  const [tabValue, setTabValue] = useState(0);

  if (!raw) {
    return null;
  }

  const rawMessageText = raw.raw_message_text || '';
  const rawResponse = raw.raw_response || {};
  const rawRequest = raw.raw_request || {};

  // Try to pretty-print the response body if it is JSON.
  let prettyResponse = '';
  try {
    prettyResponse = JSON.stringify(rawResponse, null, 2);
  } catch (e) {
    prettyResponse = String(rawResponse);
  }

  // Compose the system + user prompt so the user sees what was sent.
  let promptText = '';
  try {
    const messages = rawRequest.messages || [];
    promptText = messages
      .map((m) => `[${m.role}]\n${m.content}`)
      .join('\n\n---\n\n');
  } catch (e) {
    promptText = '(unable to render prompt)';
  }

  const hasContent = !!(rawMessageText || prettyResponse || promptText);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth>
      <DialogTitle sx={{ pr: 6 }}>
        Raw DeepSeek response
        <IconButton
          aria-label="close"
          onClick={onClose}
          sx={{ position: 'absolute', right: 8, top: 8 }}
        >
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      <DialogContent dividers sx={{ p: 0 }}>
        <Box sx={{ px: 3, py: 2 }}>
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            {raw.prompt_version && (
              <Chip size="small" label={`prompt: ${raw.prompt_version}`} color="primary" variant="outlined" />
            )}
            {raw.model && (
              <Chip size="small" label={`model: ${raw.model}`} variant="outlined" />
            )}
            {raw.validated_ir_summary?.circuit_type && (
              <Chip
                size="small"
                label={`type: ${raw.validated_ir_summary.circuit_type}`}
                variant="outlined"
              />
            )}
            <Chip
              size="small"
              label={`components: ${raw.validated_ir_summary?.component_count ?? 0}`}
              variant="outlined"
            />
            <Chip
              size="small"
              label={`subsystems: ${raw.validated_ir_summary?.subsystem_count ?? 0}`}
              variant="outlined"
            />
          </Stack>
        </Box>

        {!hasContent ? (
          <Box sx={{ p: 4, textAlign: 'center' }}>
            <Typography variant="h6" gutterBottom>
              No raw DeepSeek response was retained
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              This design was generated before the v2 prompt upgrade added raw-response
              persistence, or DeepSeek was not used (the rule-based parser handled it).
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Create a new design with the same description — the v2 prompt and the
              new &nbsp;<code>source.raw_response</code>&nbsp; field will be persisted
              automatically, and this dialog will show the model&apos;s text, the
              upstream response, and the sent prompt.
            </Typography>
          </Box>
        ) : (
          <>
            <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
              <Tabs value={tabValue} onChange={(_, v) => setTabValue(v)}>
                <Tab label="Model text" />
                <Tab label="Full upstream JSON" />
                <Tab label="Sent prompt" />
              </Tabs>
            </Box>

            <Box sx={{ p: 3 }}>
              <TabPanel value={tabValue} index={0}>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                  The exact text the model emitted (already parsed as JSON for the IR).
                </Typography>
                <CodeBlock text={rawMessageText || '(empty)'} maxHeight={460} />
              </TabPanel>

              <TabPanel value={tabValue} index={1}>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                  The full response body from the DeepSeek API (usage, finish_reason, id, ...).
                </Typography>
                <CodeBlock text={prettyResponse} maxHeight={460} />
              </TabPanel>

              <TabPanel value={tabValue} index={2}>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                  The exact system + user messages that were sent to the model.
                </Typography>
                <CodeBlock text={promptText || '(empty)'} maxHeight={460} />
              </TabPanel>
            </Box>
          </>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}
