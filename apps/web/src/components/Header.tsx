'use client';

import { Download, ShoppingCart, WifiOff } from 'lucide-react';
import { useEffect, useState } from 'react';

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

export function Header({ online }: { online: boolean }) {
  const [installEvent, setInstallEvent] = useState<BeforeInstallPromptEvent | null>(null);

  useEffect(() => {
    const onPrompt = (e: Event) => {
      e.preventDefault();
      setInstallEvent(e as BeforeInstallPromptEvent);
    };
    const onInstalled = () => setInstallEvent(null);
    window.addEventListener('beforeinstallprompt', onPrompt);
    window.addEventListener('appinstalled', onInstalled);
    return () => {
      window.removeEventListener('beforeinstallprompt', onPrompt);
      window.removeEventListener('appinstalled', onInstalled);
    };
  }, []);

  const install = async () => {
    if (!installEvent) return;
    await installEvent.prompt();
    await installEvent.userChoice;
    setInstallEvent(null);
  };

  return (
    <header className="sticky top-0 z-30 border-b border-slate-200/70 bg-white/85 backdrop-blur supports-[backdrop-filter]:bg-white/70">
      <div className="mx-auto flex h-14 max-w-xl items-center justify-between px-4">
        <a href="/" className="flex items-center gap-2" aria-label="Linktem 홈">
          <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-brand-600 text-white shadow-sm">
            <ShoppingCart size={18} strokeWidth={2.5} aria-hidden />
          </span>
          <span className="text-xl font-extrabold tracking-tight text-slate-900">
            Link<span className="text-brand-600">tem</span>
          </span>
        </a>

        <div className="flex items-center gap-2">
          {!online && (
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2.5 py-1 text-xs font-semibold text-amber-800">
              <WifiOff size={13} aria-hidden />
              오프라인
            </span>
          )}
          {installEvent && (
            <button
              type="button"
              onClick={install}
              className="inline-flex items-center gap-1 rounded-full bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white active:scale-95"
            >
              <Download size={13} aria-hidden />
              앱 설치
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
