import { Storage } from './storage.js';
import { qs, on } from './domUtils.js';

const DEFAULTS = {
    model: 'gemini-2.5-flash',
    temperature: 0.3,
    top_p: 0.9,
    top_k: 40,
    max_tokens: 1024
};

export class LLMSettingsModal {
    constructor(storageKey = 'llmSettings', onSave) {
        this.storageKey = storageKey;
        this.onSave = onSave;
        this.state = Storage.load(storageKey, DEFAULTS);
        this.modal = null;
    }

    init() {
        this.modal = qs('#llmSettingsModal');
        const openBtn = qs('#llmSettingsBtn');
        const closeBtn = qs('#llmSettingsClose');
        const saveBtn = qs('#llmSettingsSave');

        on(openBtn, 'click', () => this.show());
        on(closeBtn, 'click', () => this.hide());
        on(saveBtn, 'click', () => this.save());

        this.applyToForm();
    }

    show() {
        if (this.modal) this.modal.classList.add('open');
    }

    hide() {
        if (this.modal) this.modal.classList.remove('open');
    }

    applyToForm() {
        const modelEl = qs('#llmModel');
        if (modelEl) modelEl.value = this.state.model;
        const tempEl = qs('#llmTemp');
        if (tempEl) tempEl.setAttribute('value', this.state.temperature);
        const topP = qs('#llmTopP');
        if (topP) topP.setAttribute('value', this.state.top_p);
        const topK = qs('#llmTopK');
        if (topK) topK.setAttribute('value', this.state.top_k);
        const maxTok = qs('#llmMaxTokens');
        if (maxTok) maxTok.setAttribute('value', this.state.max_tokens);
    }

    save() {
        const model = qs('#llmModel')?.value || DEFAULTS.model;
        const temperature = parseFloat(qs('#llmTemp')?.value) || DEFAULTS.temperature;
        const top_p = parseFloat(qs('#llmTopP')?.value) || DEFAULTS.top_p;
        const top_k = parseInt(qs('#llmTopK')?.value) || DEFAULTS.top_k;
        const max_tokens = parseInt(qs('#llmMaxTokens')?.value) || DEFAULTS.max_tokens;

        this.state = { model, temperature, top_p, top_k, max_tokens };
        Storage.save(this.storageKey, this.state);
        this.onSave?.(this.state);
        this.hide();
    }
}

