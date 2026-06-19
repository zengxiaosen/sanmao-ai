import { useEffect, useState } from 'react';
import { API, showError } from '../../helpers';

export function useEnabledChannelModels(t) {
  const [enabledModels, setEnabledModels] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let mounted = true;

    const loadEnabledModels = async () => {
      setLoading(true);
      try {
        const res = await API.get('/api/channel/models_enabled');
        const { success, message, data } = res.data;
        if (!mounted) return;

        if (success) {
          setEnabledModels(Array.isArray(data) ? data : []);
        } else {
          showError(message);
        }
      } catch (error) {
        if (!mounted) return;
        console.error(t('获取启用模型失败:'), error);
        showError(t('获取启用模型失败'));
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    loadEnabledModels();

    return () => {
      mounted = false;
    };
  }, [t]);

  return { enabledModels, loading };
}
