import React, { useState, useEffect } from 'react';
import type { Platform } from './BottomNav';
import type { ChatInfo } from '../App';
import api from '../services/api';

interface Chat extends ChatInfo {
  avatar: string;
  last_message_text: string;
  last_message_at: string;
  unread_count: number;
}

interface ChatListProps {
  platform: Platform;
  onChatClick: (chat: ChatInfo) => void;
}

const ChatList: React.FC<ChatListProps> = ({ platform, onChatClick }) => {
  const [chats, setChats] = useState<Chat[]>([]);
  const [loading, setLoading] = useState(true);
  const [hasAccount, setHasAccount] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        // Проверяем, подключен ли аккаунт
        const accRes = await api.getAccounts();
        const isConnected = accRes.data.some((a: any) => a.platform === platform && a.status === 'connected');
        setHasAccount(isConnected);

        if (isConnected) {
          const res = await api.getChats(platform);
          setChats(res.data);
        }
      } catch (error) {
        console.error('Failed to fetch chats', error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [platform]);

  const platformTitle = platform === 'vk' ? 'VK' : platform === 'max' ? 'MAX' : 'Instagram';

  if (loading) return <div className="p-4 text-center text-gray-500">Загрузка...</div>;

  if (!hasAccount) {
    return (
      <div className="flex flex-col">
        <header className="p-4 text-xl font-semibold border-b border-gray-200 dark:border-gray-700">
          {platformTitle}
        </header>
        <div className="p-8 text-center text-gray-500 mt-10">
          <p className="mb-2">Аккаунт не подключен.</p>
          <p className="text-sm">Перейдите в Настройки, чтобы добавить аккаунт {platformTitle}.</p>
        </div>
      </div>
    );
  }

  if (chats.length === 0) {
    return (
      <div className="flex flex-col">
        <header className="p-4 text-xl font-semibold border-b border-gray-200 dark:border-gray-700">
          {platformTitle}
        </header>
        <div className="p-8 text-center text-gray-500 mt-10">Нет диалогов</div>
      </div>
    );
  }

  return (
    <div className="flex flex-col">
      <header className="p-4 text-xl font-semibold border-b border-gray-200 dark:border-gray-700">
        {platformTitle}
      </header>
      
      <div className="px-4 py-2">
        <input 
          type="text" 
          placeholder="🔍 Поиск" 
          className="w-full bg-gray-100 dark:bg-[#242f3d] rounded-lg px-4 py-2 text-sm outline-none"
        />
      </div>

      {chats.map((chat) => (
        <div 
          key={chat.id} 
          onClick={() => onChatClick({ id: chat.id, title: chat.title })}
          className="flex items-center px-4 py-3 hover:bg-gray-50 dark:hover:bg-[#202b36] cursor-pointer transition-colors"
        >
          <div className="w-12 h-12 rounded-full mr-3 bg-gradient-to-r from-pink-500 to-purple-500 flex items-center justify-center text-white font-bold text-lg">
            {chat.title?.charAt(0) || '?'}
          </div>
          <div className="flex-1 border-b border-gray-100 dark:border-gray-800 pb-3">
            <div className="flex justify-between items-center">
              <span className="font-medium text-[15px]">{chat.title}</span>
              <span className="text-xs text-gray-500">
                {chat.last_message_at ? new Date(chat.last_message_at).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'}) : ''}
              </span>
            </div>
            <div className="flex justify-between items-center mt-1">
              <span className="text-sm text-gray-500 truncate max-w-[200px]">{chat.last_message_text}</span>
              {chat.unread_count > 0 && (
                <span className="bg-[#3ea6ff] text-white text-xs rounded-full px-2 py-0.5 ml-2">
                  {chat.unread_count}
                </span>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

export default ChatList;