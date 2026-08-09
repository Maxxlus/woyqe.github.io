import axios from 'axios';

const getInitData = (): string => {
  const tg = (window as any).Telegram?.WebApp;
  if (tg) {
    return tg.initData;
  }
  return "query_id=AAHdF6IQAAAAAN0XohDhrOrc&user=%7B%22id%22%3A278423846%2C%22first_name%22%3A%22Admin%22%7D&auth_date=1691234567&hash=1234567890abcdefghijklmnopqrstuvwxyz1234";
};

const api = axios.create({
  baseURL: import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
    'X-Telegram-Init-Data': getInitData(),
  },

  
});

export default {
  getChats: (platform?: string) => api.get('/api/chats', { params: { platform } }),
  getMessages: (chatId: string) => api.get(`/api/chats/${chatId}/messages`),
  sendMessage: (chatId: string, text: string) => api.post(`/api/chats/${chatId}/messages`, { text }),
  connectInstagram: (username: string, password: string) => api.post('/api/accounts/instagram/connect', { username, password }),
  getAccounts: () => api.get('/api/accounts'),
  startConnection: (platform: string, payload?: any) => api.post(`/api/accounts/${platform}/connect`, payload),
  getConnectionStatus: (connectionId: string) => api.get(`/api/accounts/connections/${connectionId}`),
  cancelConnection: (connectionId: string) => api.post(`/api/accounts/connections/${connectionId}/cancel`),
  verifyConnection: (connectionId: string, code: string) => api.post(`/api/accounts/connections/${connectionId}/verify`, { code }),
  deleteAccount: (accountId: string) => api.delete(`/api/accounts/${accountId}`),
};
