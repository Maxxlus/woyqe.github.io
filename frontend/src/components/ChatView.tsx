import React, { useState, useEffect } from 'react';
import { supabase, subscribeToMessages } from '../services/realtime';
import type { ChatInfo } from '../App';
import api from '../services/api';

interface Message {
  id: string;
  text: string;
  direction: string;
  status?: string;
}

const ChatView: React.FC<{ chat: ChatInfo, onBack: () => void }> = ({ chat, onBack }) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isSending, setIsSending] = useState(false);

  useEffect(() => {
    const loadMessages = async () => {
      try {
        const res = await api.getMessages(chat.id);
        setMessages(res.data);
      } catch (error) {
        console.error("Failed to load messages", error);
      }
    };
    loadMessages();

    const subscription = subscribeToMessages(chat.id, (payload) => {
      setMessages((prev) => [...prev, payload.new]);
    });

    return () => {
      supabase.removeChannel(subscription);
    };
  }, [chat.id]);

  const handleSend = async () => {
    if (!input.trim() || isSending) return;
    
    const tempId = `temp-${Date.now()}`;
    const tempMessage: Message = { id: tempId, text: input, direction: 'outgoing', status: 'sending' };
    
    setMessages((prev) => [...prev, tempMessage]);
    const textToSend = input;
    setInput('');
    setIsSending(true);

    try {
      await api.sendMessage(chat.id, textToSend);
      setMessages((prev) => prev.map(m => m.id === tempId ? { ...m, status: 'sent' } : m));
    } catch (error) {
      setMessages((prev) => prev.map(m => m.id === tempId ? { ...m, status: 'failed' } : m));
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <header className="flex items-center p-3 border-b border-gray-200 dark:border-gray-700 sticky top-0 bg-white dark:bg-[#17212b] z-10">
        <button onClick={onBack} className="mr-4 text-blue-500 text-xl">←</button>
        <div className="w-10 h-10 rounded-full mr-3 bg-gradient-to-r from-pink-500 to-purple-500 flex items-center justify-center text-white font-bold">
          {chat.title.charAt(0)}
        </div>
        <div>
          <div className="font-medium">{chat.title}</div>
          <div className="text-xs text-gray-500">был недавно</div>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-4 space-y-2 bg-gray-50 dark:bg-[#0e1621]">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.direction === 'outgoing' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[70%] px-3 py-2 rounded-2xl text-[15px] ${
              msg.direction === 'outgoing' 
                ? 'bg-[#2f5bfd] text-white rounded-br-md' 
                : 'bg-white dark:bg-[#182533] rounded-bl-md'
            }`}>
              {msg.text}
              {msg.status === 'sending' && <span className="text-xs ml-2 opacity-50">⏳</span>}
              {msg.status === 'failed' && <span className="text-xs ml-2 text-red-300">⚠</span>}
            </div>
          </div>
        ))}
      </div>

      <footer className="p-3 border-t border-gray-200 dark:border-gray-700 flex items-center bg-white dark:bg-[#17212b]">
        <button className="text-gray-400 text-2xl mr-3">+</button>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Написать сообщение..."
          className="flex-1 bg-gray-100 dark:bg-[#242f3d] rounded-xl px-4 py-2 outline-none text-white"
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
        />
        <button onClick={handleSend} className="ml-3 text-blue-500 text-2xl">➤</button>
      </footer>
    </div>
  );
};

export default ChatView;