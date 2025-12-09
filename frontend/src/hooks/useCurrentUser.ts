import { useEffect, useState } from 'react';
import { supabase } from '../lib/supabaseClient';

type UserProfile = {
  id: string;
  username: string | null;
  role: 'admin' | 'author' | 'participant';
};

export function useCurrentUser() {
  const [loading, setLoading] = useState(true);
  const [profile, setProfile] = useState<UserProfile | null>(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true);

      const {
        data: { user },
        error: userError,
      } = await supabase.auth.getUser();

      if (userError || !user) {
        setProfile(null);
        setLoading(false);
        return;
      }

      const { data, error } = await supabase
        .from('user_profiles')
        .select('*')
        .eq('id', user.id)
        .single();

      if (error) {
        console.error('Error loading profile', error);
        setProfile(null);
      } else {
        setProfile(data as UserProfile);
      }

      setLoading(false);
    };

    load();

    // подписка на изменение состояния auth (вход/выход)
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, _session) => {
      load();
    });

    return () => {
      subscription.unsubscribe();
    };
  }, []);

  return { loading, profile };
}
