import React, { useState, useEffect } from 'react';
import api from '../services/api';
import AddAccount from './AddAccount';

interface Account {
  id: string;
  platform: string;
  username: string;
  status: string;
}

const Settings: React.FC<{ onBack: () => void }> = ({ onBack }) => {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [showAddAccount, setShowAddAccount] = useState(false);

  const fetchAccounts = async () => {
    try {
      const res = await api.getAccounts();
      setAccounts(res.data);
    } catch (error) {
      console.error(error);
    }
  };

  useEffect(() => {
    fetchAccounts();
  }, []);

  if (showAddAccount) {
    return <AddAccount onClose={() => { setShowAddAccount(false); fetchAccounts(); }} />;
  }

  return (
    <div className="p-4">
      <header className="flex items-center mb-6">
        <button onClick={onBack} className="mr-4 text-blue-500 text-xl">←</button>
        <h1 className="text-xl font-semibold">Настройки</h1>
      </header>

      <div className="mb-8">
        <h2 className="text-gray-500 text-sm mb-3">Подключённые аккаунты</h2>
        
        {accounts.length === 0 ? (
          <p className="text-gray-400 text-sm">Нет подключённых аккаунтов</p>
        ) : (
          accounts.map(acc => (
            <div key={acc.id} className="flex items-center justify-between p-3 bg-gray-50 dark:bg-[#0e1621] rounded-xl mb-2">
              <div className="flex items-center">
                <span className="capitalize font-medium mr-2">{acc.platform}</span>
                {acc.username && <span className="text-gray-400 text-sm">@{acc.username}</span>}
              </div>
              <div className="flex items-center">
                {acc.status === 'connected' ? (
                  <span className="text-green-500 text-xs">● Подключён</span>
                ) : (
                  <span className="text-red-500 text-xs">● Ошибка</span>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      <button 
        onClick={() => setShowAddAccount(true)}
        className="w-full bg-[#2f5bfd] text-white rounded-xl py-3 font-medium"
      >
        + Добавить аккаунт
      </button>
    </div>
  );
};

export default Settings;