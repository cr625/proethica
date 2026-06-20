(function() {
    const TEMPLATE_STORAGE_KEY = 'proethica_prompt_editor_template';
    const DEFAULT_URL = window.PROMPT_EDITOR_REDIRECT.defaultUrl;

    try {
        const saved = localStorage.getItem(TEMPLATE_STORAGE_KEY);
        if (saved) {
            const { url } = JSON.parse(saved);
            if (url && url.startsWith('/tools/prompts/')) {
                window.location.replace(url);
                return;
            }
        }
    } catch (e) {
        console.warn('Failed to restore template location:', e);
    }

    // Default redirect
    window.location.replace(DEFAULT_URL);
})();
