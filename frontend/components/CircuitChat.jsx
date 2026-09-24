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
  Tooltip,
  IconButton,
} from '@mui/material';
import AttachFileIcon from '@mui/icons-material/AttachFile';
import SendIcon from '@mui/icons-material/Send';
import CloseIcon from '@mui/icons-material/Close';
import DescriptionIcon from '@mui/icons-material/Description';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import PersonIcon from '@mui/icons-material/Person';
import { API_BASE_URL } from '../config.mjs';
import { formatUserError } from '../lib/errorUtils';

const MAX_ATTACHMENTS = 4;
const TEXT_EXTENSIONS = /\.(txt|md|markdown|csv|log|json)$/i;

// Downscale + re-encode an image file client-side so the base64 payload (and
// the copy persisted in chat_messages) stays small. White background first:
// pasted UI screenshots are often transparent PNGs.
function compressImage(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('无法读取图片文件'));
    reader.onload = () => {
      const img = new window.Image();
      img.onerror = () => reject(new Error('图片解码失败'));
      img.onload = () => {
        const maxSide = 1280;
        const scale = Math.min(1, maxSide / Math.max(img.width, img.height));
        const canvas = document.createElement('canvas');
        canvas.width = Math.max(1, Math.round(img.width * scale));
        canvas.height = Math.max(1, Math.round(img.height * scale));
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        resolve(canvas.toDataURL('image/jpeg', 0.85));
      };
      img.src = reader.result;
    };
    reader.readAsDataURL(file);
  });
}

function readFileAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('无法读取文件'));
    reader.onload = () => resolve(String(reader.result).split(',')[1]);
    reader.readAsDataURL(file);
  });
}

function AttachmentPreview({ attachment, onRemove }) {
  if (attachment.kind === 'image') {
    return (
      <Box sx={{ position: 'relative', flexShrink: 0 }}>
        <Box
          component="img"
          src={attachment.previewUrl}
          alt={attachment.name}
          sx={{
            width: 56, height: 56, objectFit: 'cover',
            borderRadius: 1.5, border: '1px solid', borderColor: 'divider',
            display: 'block',
          }}
        />
        {onRemove && (
          <IconButton
            size="small"
            onClick={onRemove}
            sx={{
              position: 'absolute', top: -8, right: -8,
              bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider',
              '&:hover': { bgcolor: 'action.hover' },
              width: 20, height: 20, p: 0.2,
            }}
          >
            <CloseIcon sx={{ fontSize: 14 }} />
          </IconButton>
        )}
      </Box>
    );
  }
  return (
    <Chip
      icon={<DescriptionIcon />}
      label={attachment.name}
      onDelete={onRemove}
      size="small"
      variant="outlined"
      sx={{ maxWidth: 220 }}
    />
  );
}

function MessageAttachments({ attachments = [] }) {
  return (
    <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap"
      sx={{ justifyContent: 'flex-end', mb: 0.5 }}>
      {attachments.map((a, i) => (
        a.kind === 'image' ? (
          <Box key={i}
            component="img"
            src={`data:${a.mime_type || 'image/png'};base64,${a.data_base64}`}
            alt={a.name}
            sx={{
              maxHeight: 140, maxWidth: 240, objectFit: 'contain',
              borderRadius: 1.5, border: '1px solid', borderColor: 'divider',
            }}
          />
        ) : (
          <Chip key={i} icon={<DescriptionIcon />} label={a.name} size="small" variant="outlined" />
        )
      ))}
    </Stack>
  );
}

function ChatMessage({ message }) {
  const isUser = message.role === 'user';
  return (
    <Stack
      direction="row"
      spacing={1}
      sx={{ justifyContent: isUser ? 'flex-end' : 'flex-start', mb: 1.5, alignItems: 'flex-start' }}
    >
      {!isUser && (
        <Box sx={{
          mt: 0.25, width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
          bgcolor: 'primary.main', color: 'primary.contrastText',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <SmartToyIcon sx={{ fontSize: 16 }} />
        </Box>
      )}
      <Box sx={{ maxWidth: '82%' }}>
        {(message.attachments || []).length > 0 && (
          <MessageAttachments attachments={message.attachments} />
        )}
        {message.content && (
          <Paper
            elevation={0}
            sx={{
              px: 1.5, py: 1, borderRadius: 2.5,
              borderTopRightRadius: isUser ? 0.5 : 2.5,
              borderTopLeftRadius: isUser ? 2.5 : 0.5,
              border: '1px solid',
              borderColor: isUser ? 'primary.main' : 'divider',
              bgcolor: isUser ? 'primary.lighter' : 'background.paper',
            }}
          >
            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.65, wordBreak: 'break-word' }}>
              {message.content}
            </Typography>
          </Paper>
        )}
      </Box>
      {isUser && (
        <Box sx={{
          mt: 0.25, width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
          bgcolor: 'grey.300', color: 'grey.700',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <PersonIcon sx={{ fontSize: 16 }} />
        </Box>
      )}
    </Stack>
  );
}

const EXAMPLE_PROMPTS = [
  '把 LED 换成蜂鸣器',
  '增加一个按键开关控制输出',
  '供电电压改为 12V',
];

export default function CircuitChat({ designId, chatMessages, designStatus, onRefresh, fillHeight = false }) {
  const [input, setInput] = useState('');
  const [attachments, setAttachments] = useState([]); // pending attachments of the next message
  const [sending, setSending] = useState(false);
  const [pendingMsg, setPendingMsg] = useState(null); // {role:'user', content, attachments}
  const [serverLenAtSend, setServerLenAtSend] = useState(0);
  const [chatError, setChatError] = useState(null);
  const [attachBusy, setAttachBusy] = useState(false);
  const fileInputRef = useRef(null);
  const messagesEndRef = useRef(null);
  const aliveRef = useRef(true);

  useEffect(() => {
    aliveRef.current = true;
    return () => { aliveRef.current = false; };
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView?.({ block: 'nearest' });
  }, [chatMessages?.length, pendingMsg, sending]);

  const addFiles = async (files) => {
    setChatError(null);
    const added = [];
    for (const file of files) {
      if (attachments.length + added.length >= MAX_ATTACHMENTS) {
        setChatError(`最多附带 ${MAX_ATTACHMENTS} 个附件`);
        break;
      }
      setAttachBusy(true);
      try {
        let att;
        if (file.type.startsWith('image/')) {
          const dataUrl = await compressImage(file);
          att = {
            id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
            kind: 'image',
            name: file.name || '粘贴的图片',
            mime_type: 'image/jpeg',
            data_base64: dataUrl.split(',')[1],
            previewUrl: dataUrl,
          };
        } else if (TEXT_EXTENSIONS.test(file.name)) {
          const text = await file.text();
          if (!text.trim()) {
            setChatError(`文件 ${file.name} 内容为空`);
            continue;
          }
          att = {
            id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
            kind: 'document',
            name: file.name,
            mime_type: file.type || 'text/plain',
            text: text.slice(0, 20000),
          };
        } else if (/\.pdf$/i.test(file.name) || file.type === 'application/pdf') {
          att = {
            id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
            kind: 'document',
            name: file.name,
            mime_type: 'application/pdf',
            data_base64: await readFileAsBase64(file),
          };
        } else {
          setChatError(`暂不支持 ${file.name}（支持图片、TXT/MD/CSV/JSON/LOG、PDF）`);
          continue;
        }
        added.push(att);
      } catch (e) {
        setChatError(`处理 ${file.name} 失败：${e.message}`);
      } finally {
        setAttachBusy(false);
      }
    }
    if (added.length > 0) {
      setAttachments((prev) => [...prev, ...added].slice(0, MAX_ATTACHMENTS));
    }
  };

  const send = async () => {
    const text = input.trim();
    if ((!text && attachments.length === 0) || sending) return;
    setChatError(null);
    const sentAttachments = attachments.map(({ id, previewUrl, ...rest }) => {
      // strip UI-only fields; undefined values are dropped by JSON.stringify
      const clean = {};
      for (const [k, v] of Object.entries(rest)) {
        if (v !== undefined && v !== null && v !== '') clean[k] = v;
      }
      return clean;
    });
    setPendingMsg({ role: 'user', content: text, attachments: sentAttachments });
    setServerLenAtSend((chatMessages || []).length);
    setSending(true);
    setInput('');
    setAttachments([]);
    try {
      const response = await fetch(`${API_BASE_URL}/circuit/${designId}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, attachments: sentAttachments }),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail.detail || `请求失败 (${response.status})`);
      }
      // 后续进度/完成由 WebSocket/轮询驱动父组件刷新 design 实现
    } catch (e) {
      if (aliveRef.current) {
        setSending(false);
        setPendingMsg(null);
        setChatError(formatUserError('发送修改指令', e));
        setInput(text);
        setAttachments(sentAttachments.map((a, i) => ({
          ...a,
          id: `restore-${i}`,
          previewUrl: a.kind === 'image' ? `data:${a.mime_type};base64,${a.data_base64}` : undefined,
        })));
      }
    }
  };

  useEffect(() => {
    if (sending && designStatus === 'completed') {
      setSending(false);
      setPendingMsg(null);
    }
  }, [sending, designStatus]);

  // 轮询降级兜底：WebSocket 不可用时父组件不会推送修改进度，这里自己
  // 轻量轮询 status，完成后让父组件拉取最新设计数据
  useEffect(() => {
    if (!sending) return undefined;
    const timer = setInterval(async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/circuit/${designId}/status`, { cache: 'no-store' });
        if (!response.ok) return;
        const data = await response.json();
        if (data.status === 'completed' || data.status === 'failed') {
          setSending(false);
          setPendingMsg(null);
          onRefresh?.();
        }
      } catch { /* transient network errors are retried on the next tick */ }
    }, 3000);
    return () => clearInterval(timer);
  }, [sending, designId]);

  const serverMessages = chatMessages || [];
  const showPendingUser = pendingMsg && serverMessages.length <= serverLenAtSend;
  const busy = sending || designStatus === 'processing';

  return (
    <Paper elevation={0} sx={{
      p: 1.5,
      mt: fillHeight ? 0 : 2,
      border: '1px solid', borderColor: 'divider',
      ...(fillHeight
        ? { height: '100%', display: 'flex', flexDirection: 'column', minHeight: 150, overflow: 'hidden' }
        : {}),
    }}>
      <Typography variant="subtitle2" fontWeight="bold" sx={{ mb: 1, flexShrink: 0 }}>
        对话修改电路
        <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 1.5 }}>
          描述修改要求，可粘贴图片（如参考电路截图）或上传文档作为依据
        </Typography>
      </Typography>

      <Box sx={{
        flex: fillHeight ? '1 1 auto' : undefined,
        minHeight: fillHeight ? 48 : 80,
        maxHeight: fillHeight ? undefined : 380,
        overflowY: 'auto', pr: 0.5,
      }}>
        {serverMessages.map((m, i) => (
          <ChatMessage key={i} message={m} />
        ))}
        {showPendingUser && <ChatMessage message={pendingMsg} />}
        {sending && (
          <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 1.5 }}>
            <Box sx={{
              width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
              bgcolor: 'primary.main', color: 'primary.contrastText',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <SmartToyIcon sx={{ fontSize: 16 }} />
            </Box>
            <Typography variant="body2" color="text.secondary">
              正在修改电路并重新生成原理图、仿真与解读…
            </Typography>
            <CircularProgress size={14} />
          </Stack>
        )}
        {!busy && serverMessages.length === 0 && !showPendingUser && (
          <Stack spacing={1} sx={{ py: 1 }}>
            <Typography variant="caption" color="text.secondary">
              试试：
            </Typography>
            <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
              {EXAMPLE_PROMPTS.map((p) => (
                <Chip
                  key={p}
                  label={p}
                  size="small"
                  variant="outlined"
                  clickable
                  onClick={() => setInput(p)}
                />
              ))}
            </Stack>
          </Stack>
        )}
        <div ref={messagesEndRef} />
      </Box>

      {chatError && (
        <Alert severity="error" sx={{ mt: 1 }} onClose={() => setChatError(null)}>
          {chatError}
        </Alert>
      )}

      {/* 输入区（ChatGPT 风格） */}
      <Box sx={{
        mt: 1, border: '1px solid', borderColor: busy ? 'divider' : 'primary.main',
        borderRadius: 3, p: 1, position: 'relative',
        transition: 'border-color .2s', flexShrink: 0,
      }}>
        {attachments.length > 0 && (
          <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap" sx={{ p: 1, pb: 1.5 }}>
            {attachments.map((att) => (
              <AttachmentPreview
                key={att.id}
                attachment={att}
                onRemove={busy ? undefined : () => setAttachments(attachments.filter((a) => a.id !== att.id))}
              />
            ))}
          </Stack>
        )}
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              send();
            }
          }}
          onPaste={(e) => {
            const files = Array.from(e.clipboardData?.files || [])
              .filter((f) => f.type.startsWith('image/'));
            if (files.length > 0) {
              e.preventDefault();
              addFiles(files);
            }
          }}
          placeholder={busy ? '电路修改中…' : '描述你想要的修改…（Enter 发送，Shift+Enter 换行，可直接粘贴图片）'}
          disabled={busy}
          rows={Math.min(fillHeight ? 3 : 5, Math.max(1, input.split('\n').length))}
          style={{
            width: '100%', resize: 'none', border: 'none', outline: 'none',
            background: 'transparent', fontFamily: 'inherit',
            fontSize: '0.875rem', lineHeight: 1.6, color: 'inherit',
            padding: '8px 84px 8px 10px',
          }}
        />
        <Box sx={{ position: 'absolute', left: 8, bottom: 8 }}>
          <Tooltip title="上传图片或文档（TXT/MD/CSV/JSON/PDF）">
            <span>
              <IconButton
                size="small"
                onClick={() => fileInputRef.current?.click()}
                disabled={busy || attachBusy}
              >
                {attachBusy ? <CircularProgress size={16} /> : <AttachFileIcon fontSize="small" />}
              </IconButton>
            </span>
          </Tooltip>
        </Box>
        <Box sx={{ position: 'absolute', right: 8, bottom: 8 }}>
          <IconButton
            onClick={send}
            disabled={busy || (!input.trim() && attachments.length === 0)}
            sx={{
              bgcolor: 'primary.main', color: 'primary.contrastText',
              '&:hover': { bgcolor: 'primary.dark' },
              '&.Mui-disabled': { bgcolor: 'action.disabledBackground', color: 'action.disabled' },
              borderRadius: '50%', p: 0.75,
            }}
          >
            <SendIcon sx={{ fontSize: 18 }} />
          </IconButton>
        </Box>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept="image/*,.txt,.md,.markdown,.csv,.log,.json,.pdf"
          style={{ display: 'none' }}
          onChange={(e) => {
            addFiles(Array.from(e.target.files || []));
            e.target.value = '';
          }}
        />
      </Box>
    </Paper>
  );
}
