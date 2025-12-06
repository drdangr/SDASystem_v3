export const Storage = {
    load(key, fallback = null) {
        try {
            const raw = localStorage.getItem(key);
            if (!raw) return fallback;
            return JSON.parse(raw);
        } catch (_) {
            return fallback;
        }
    },
    save(key, value) {
        try {
            localStorage.setItem(key, JSON.stringify(value));
        } catch (_) {
            /* ignore */
        }
    }
};

