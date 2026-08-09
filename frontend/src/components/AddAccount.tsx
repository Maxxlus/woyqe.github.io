import React, { useState } from 'react';
import api from '../services/api';

type Platform = 'instagram' | 'max' | 'vk';
type Step = 'idle' | 'connecting' | 'code' | 'success' | 'error';
type CodeKind = '2fa' | 'challenge';

interface ConnState {
  step: Step;
  connectionId?: string;
  codeKind?: CodeKind;
  error?: string;
}

const AddAccount: React.FC<{ onClose: () => void }> = ({ onClose }) => {
  const [activeTab, setActiveTab] = useState<Platform>('instagram');
  const [igCreds, setIgCreds] = useState({ username: '', password: '' });
  const [state, setState] = useState<ConnState>({ step: 'idle' });
  const [code, setCode] = useState('');

  const resetTab = (tab: Platform) => {
    setActiveTab(tab);
    setState({ step: 'idle' });
    setCode('');
  };

  const handleInstagramLogin = async () => {
    setState({ step: 'connecting' });
    try {
      const res = await api.startConnection('instagram', igCreds);
      const status = res.data.status;
      if (status === 'connected') {
        setState({ step: 'success' });
        setTimeout(onClose, 1200);
      } else if (status === '2fa_required') {
        setState({ step: 'code', connectionId: res.data.connection_id, codeKind: '2fa' });
      } else if (status === 'challenge_required') {
        setState({ step: 'code', connectionId: res.data.connection_id, codeKind: 'challenge' });
      } else {
        setState({ step: 'error', error: res.data.error || 'Не удалось войти' });
      }
    } catch (error: any) {
      setState({ step: 'error', error: error.response?.data?.detail || 'Ошибка сети' });
    }
  };

  const handleVerifyCode = async () => {
    if (!state.connectionId || !code.trim()) return;
    const { connectionId, codeKind } = state;
    setState({ step: 'connecting' });
    try {
      const res = await api.verifyConnection(connectionId, code.trim());
      if (res.data.status === 'connected') {
        setState({ step: 'success' });
        setTimeout(onClose, 1200);
      } else {
        setState({ step: 'code', connectionId, codeKind, error: res.data.error || 'Неверный код' });
      }
    } catch (error: any) {
      setState({ step: 'code', connectionId, codeKind, error: error.response?.data?.detail || 'Ошибка сети' });
    }
  };

  const renderInstagram = () => {
    if (state.step === 'connecting') {
      return (
        <div className="flex flex-col items-center p-10 text-gray-500">
          <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mb-4" />
          <p>Подключаемся к Instagram…</p>
        </div>
      );
    }

    if (state.step === 'code') {
      const isChallenge = state.codeKind === 'challenge';
      return (
        <div className="p-4">
          <h2 className="text-lg font-semibold mb-2">
            {isChallenge ? 'Подтверждение личности' : 'Двухфакторная аутентификация'}
          </h2>
          <p className="text-gray-400 text-sm mb-4">
            {isChallenge
              ? 'Instagram отправил код на вашу почту или телефон. Введите его.'
              : 'Введите код из приложения-аутентификатора или SMS.'}
          </p>
          {state.error && <p className="text-red-500 text-sm mb-3">{state.error}</p>}
          <input
            type="text"
            inputMode="numeric"
            placeholder="Код"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            className="w-full bg-gray-100 dark:bg-[#242f3d] rounded-lg px-4 py-3 mb-4 outline-none text-center text-xl tracking-widest"
          />
          <button
            onClick={handleVerifyCode}
            disabled={!code.trim()}
            className="w-full bg-[#2f5bfd] text-white rounded-xl py-3 font-medium disabled:opacity-50"
          >
            Подтвердить
          </button>
        </div>
      );
    }

    if (state.step === 'success') {
      return (
        <div className="flex flex-col items-center p-8">
          <div className="w-16 h-16 bg-green-500 rounded-full flex items-center justify-center text-white text-3xl mb-4">✓</div>
          <h2 className="text-xl font-semibold">Аккаунт подключён</h2>
          <p className="text-gray-400 text-sm mt-1">Загружаем ваши диалоги…</p>
        </div>
      );
    }

    // idle or error → login form
    return (
      <div className="p-4">
        <h2 className="text-lg font-semibold mb-2">Подключение личного аккаунта</h2>
        <p className="text-gray-400 text-sm mb-4">Введите данные для входа в Instagram. Пароль не сохраняется.</p>
        {state.step === 'error' && <p className="text-red-500 text-sm mb-3">{state.error}</p>}
        <input
          type="text"
          placeholder="Имя пользователя"
          value={igCreds.username}
          onChange={(e) => setIgCreds({ ...igCreds, username: e.target.value })}
          className="w-full bg-gray-100 dark:bg-[#242f3d] rounded-lg px-4 py-3 mb-2 outline-none"
        />
        <input
          type="password"
          placeholder="Пароль"
          value={igCreds.password}
          onChange={(e) => setIgCreds({ ...igCreds, password: e.target.value })}
          className="w-full bg-gray-100 dark:bg-[#242f3d] rounded-lg px-4 py-3 mb-4 outline-none"
        />
        <button
          onClick={handleInstagramLogin}
          disabled={!igCreds.username || !igCreds.password}
          className="w-full bg-[#2f5bfd] text-white rounded-xl py-3 font-medium disabled:opacity-50"
        >
          Подключить
        </button>
      </div>
    );
  };

  const renderComingSoon = (name: string) => (
    <div className="p-8 text-center text-gray-500">
      <p className="mb-1">{name} появится в ближайшем обновлении.</p>
      <p className="text-sm">Сейчас доступно подключение Instagram.</p>
    </div>
  );

  return (
    <div className="flex flex-col h-full">
      <header className="flex items-center p-4 border-b border-gray-200 dark:border-gray-700">
        <button onClick={onClose} className="mr-4 text-blue-500 text-xl">←</button>
        <h1 className="text-xl font-semibold">Добавить аккаунт</h1>
      </header>

      <div className="grid border-b border-gray-200 dark:border-gray-700" style={{ gridTemplateColumns: 'repeat(3, minmax(0, 1fr))' }}>
        {([['instagram', 'Inst'], ['max', 'MAX'], ['vk', 'VK']] as [Platform, string][]).map(([tab, label]) => (
          <button
            key={tab}
            onClick={() => resetTab(tab)}
            className={`py-3 text-sm font-medium ${
              activeTab === tab ? 'text-blue-500 border-b-2 border-blue-500' : 'text-gray-500'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto">
        {activeTab === 'instagram' && renderInstagram()}
        {activeTab === 'max' && renderComingSoon('MAX')}
        {activeTab === 'vk' && renderComingSoon('VK')}
      </div>
    </div>
  );
};

export default AddAccount;
