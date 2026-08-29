import { useState, useEffect, useCallback } from 'react';
import { AuthConfigResponse } from '../../types/api';

export function useAuth() {
  const [config, setConfig] = useState<AuthConfigResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchConfig = useCallback(async () => {
    try {
      const res = await fetch('http://localhost:8000/api/auth/config');
      if (res.ok) setConfig(await res.json());
    } catch (err) { console.error(err); } 
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchConfig(); }, [fetchConfig]);

  const switchMode = async (mode: 'oauth' | 'service_account', email?: string) => {
    await fetch('http://localhost:8000/api/auth/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ auth_mode: mode, delegated_user_email: email }),
    });
    fetchConfig();
  };

  const startOAuthPopup = async () => {
    const res = await fetch('http://localhost:8000/api/auth/oauth/start', { method: 'POST' });
    const data = await res.json();
    const popup = window.open(data.authorization_url, 'panopticon_auth', 'width=600,height=700,status=no,toolbar=no,menubar=no');
    
    const messageHandler = (event: MessageEvent) => {
      if (event.data?.type === 'PANOPTICON_OAUTH_SUCCESS') {
        window.removeEventListener('message', messageHandler);
        if (popup) popup.close();
        fetchConfig();
      }
    };
    window.addEventListener('message', messageHandler);
  };

  const uploadCredentials = async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    await fetch('http://localhost:8000/api/auth/credentials/upload', { method: 'POST', body: formData });
    fetchConfig();
  };

  return { config, loading, switchMode, startOAuthPopup, uploadCredentials };
}
