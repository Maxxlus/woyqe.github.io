import React from 'react';

export type Platform = 'instagram' | 'max' | 'vk';

interface BottomNavProps {
  activeTab: Platform;
  onTabChange: (tab: Platform) => void;
}

const tabs: { id: Platform; label: string }[] = [
  { id: 'instagram', label: 'Inst' },
  { id: 'max', label: 'MAX' },
  { id: 'vk', label: 'VK' },
];

const BottomNav: React.FC<BottomNavProps> = ({ activeTab, onTabChange }) => {
  return (
    <nav
      className="grid items-center bg-white dark:bg-[#17212b] border-t border-gray-200 dark:border-gray-700 py-3 pb-5"
      style={{ gridTemplateColumns: 'repeat(3, minmax(0, 1fr))' }}
    >
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onTabChange(tab.id)}
          className={`flex items-center justify-center text-base font-medium truncate ${
            activeTab === tab.id ? 'text-blue-500' : 'text-gray-500'
          }`}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  );
};

export default BottomNav;
