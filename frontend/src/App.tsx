import React, { useState } from 'react';
import ChatList from './components/ChatList';
import ChatView from './components/ChatView';
import BottomNav from './components/BottomNav';
import Settings from './components/Settings'; // Новый компонент

type Platform = 'instagram' | 'max' | 'vk';

export interface ChatInfo {
  id: string;
  title: string;
}

const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<Platform>('instagram');
  const [activeChat, setActiveChat] = useState<ChatInfo | null>(null);
  const [showSettings, setShowSettings] = useState(false);

  return (
    <div className="flex flex-col h-screen bg-white dark:bg-[#17212b] text-black dark:text-white">
      <div className="flex-1 overflow-y-auto">
        {showSettings ? (
          <Settings onBack={() => setShowSettings(false)} />
        ) : activeChat ? (
          <ChatView chat={activeChat} onBack={() => setActiveChat(null)} />
        ) : (
          <div className="relative">
            <button 
              onClick={() => setShowSettings(true)}
              className="absolute top-4 right-4 text-gray-500 text-xl z-10"
            >
              ⚙
            </button>
            <ChatList platform={activeTab} onChatClick={(chat) => setActiveChat(chat)} />
          </div>
        )}
      </div>
      
      {!showSettings && !activeChat && (
        <BottomNav activeTab={activeTab} onTabChange={setActiveTab} />
      )}
    </div>
  );
};

export default App;