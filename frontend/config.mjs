export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api').replace(/\/$/, '');
export const WEBSOCKET_URL = (process.env.NEXT_PUBLIC_WEBSOCKET_URL || 'http://localhost:8000').replace(/\/$/, '');
