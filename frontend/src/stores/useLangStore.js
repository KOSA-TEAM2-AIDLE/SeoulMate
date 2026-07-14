import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export const useLangStore = create(
    persist(
        (set) => ({
            lang: 'ko',
            toggleLang: () =>
                set((state) => ({ lang: state.lang === 'ko' ? 'en' : 'ko' })),
            setLang: (newLang) => set({ lang: newLang }),
        }),
        {
            name: 'user-language-setting',
        }
    )
);