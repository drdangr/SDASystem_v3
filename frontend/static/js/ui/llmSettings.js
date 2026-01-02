import { Storage } from './storage.js';
import { qs, on } from './domUtils.js';
import { fetchLLMServices, updateLLMService } from '../api/llmClient.js';

const DEFAULTS = {
    service_id: null,
    profile_id: null,
    model: 'gemini-2.5-flash',
    temperature: 0.3,
    top_p: 0.9,
    top_k: 40,
    max_tokens: 1024,
    embedding_backend: 'local'
};

export class LLMSettingsModal {
    constructor(storageKey = 'llmSettings', onSave) {
        this.storageKey = storageKey;
        this.onSave = onSave;
        this.state = Storage.load(storageKey, DEFAULTS);
        this.modal = null;
        this.services = [];
        this.profiles = [];
    }

    init() {
        this.modal = qs('#llmSettingsModal');
        const openBtn = qs('#llmSettingsBtn');
        const closeBtn = qs('#llmSettingsClose');
        const saveBtn = qs('#llmSettingsSave');

        on(openBtn, 'click', () => this.show());
        on(closeBtn, 'click', () => this.hide());
        on(saveBtn, 'click', () => this.save());

        this.loadServices(); // async
        this.loadEmbeddingBackend(); // async
        this.applyToForm();
    }

    show() {
        if (this.modal) this.modal.classList.add('open');
    }

    hide() {
        if (this.modal) this.modal.classList.remove('open');
    }

    async loadServices() {
        try {
            const data = await fetchLLMServices();
            this.services = data.services || [];
            this.profiles = data.profiles || [];
            // auto-pick defaults if not set
            if (!this.state.service_id && this.services.length) {
                this.state.service_id = this.services[0].id;
            }
            if (!this.state.profile_id && this.services.length) {
                const svc = this.services.find(s => s.id === this.state.service_id) || this.services[0];
                this.state.profile_id = svc.default_profile_id || (this.profiles[0]?.id || null);
            }
            this.populateSelects();
        } catch (e) {
            console.warn('Failed to load LLM services', e);
        }
    }

    populateSelects() {
        const svcSel = qs('#llmServiceSelect');
        const profSel = qs('#llmProfileSelect');
        if (svcSel) {
            svcSel.innerHTML = '';
            this.services.forEach((s) => {
                const opt = document.createElement('option');
                opt.value = s.id;
                opt.textContent = s.label || s.id;
                svcSel.appendChild(opt);
            });
            if (this.state.service_id) {
                svcSel.value = this.state.service_id;
            }
            on(svcSel, 'change', (e) => {
                this.state.service_id = e.target.value;
                const svc = this.services.find(s => s.id === this.state.service_id);
                if (svc) {
                    this.state.profile_id = svc.default_profile_id || this.state.profile_id;
                    this.applyProfileDefaults(this.state.profile_id);
                    this.applyToForm();
                }
            });
        }
        if (profSel) {
            profSel.innerHTML = '';
            this.profiles.forEach((p) => {
                const opt = document.createElement('option');
                opt.value = p.id;
                opt.textContent = p.label || p.id;
                profSel.appendChild(opt);
            });
            if (this.state.profile_id) profSel.value = this.state.profile_id;
            on(profSel, 'change', (e) => {
                this.state.profile_id = e.target.value;
                this.applyProfileDefaults(this.state.profile_id);
                this.applyToForm();
            });
        }
    }

    async loadEmbeddingBackend() {
        try {
            const response = await fetch('/api/embedding/backend');
            const data = await response.json();
            this.state.embedding_backend = data.backend || 'local';
            this.updateEmbeddingStatus(data);
        } catch (e) {
            console.warn('Failed to load embedding backend', e);
            this.state.embedding_backend = 'local';
        }
        this.applyToForm();
    }

    updateEmbeddingStatus(data) {
        const statusText = qs('#embeddingStatusText');
        const dimensionEl = qs('#embeddingDimension');
        if (statusText) {
            statusText.textContent = data.backend || 'unknown';
            statusText.style.color = data.backend === 'mock' ? '#f44336' : '#4caf50';
        }
        if (dimensionEl) {
            dimensionEl.textContent = data.dimension || '-';
        }
    }

    applyToForm() {
        // service/profile selects populated async
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
        
        // Embedding backend
        const embeddingBackendEl = qs('#embeddingBackend');
        if (embeddingBackendEl) {
            embeddingBackendEl.value = this.state.embedding_backend || 'local';
        }
    }

    applyProfileDefaults(profileId) {
        const prof = this.profiles.find(p => p.id === profileId);
        if (!prof) return;
        this.state.model = prof.model || this.state.model;
        this.state.temperature = prof.temperature ?? this.state.temperature;
        this.state.top_p = prof.top_p ?? this.state.top_p;
        this.state.top_k = prof.top_k ?? this.state.top_k;
        this.state.max_tokens = prof.max_tokens ?? this.state.max_tokens;
    }

    async save() {
        const service_id = qs('#llmServiceSelect')?.value || null;
        const profile_id = qs('#llmProfileSelect')?.value || null;
        const model = qs('#llmModel')?.value || DEFAULTS.model;
        const temperature = parseFloat(qs('#llmTemp')?.value) || DEFAULTS.temperature;
        const top_p = parseFloat(qs('#llmTopP')?.value) || DEFAULTS.top_p;
        const top_k = parseInt(qs('#llmTopK')?.value) || DEFAULTS.top_k;
        const max_tokens = parseInt(qs('#llmMaxTokens')?.value) || DEFAULTS.max_tokens;
        const embedding_backend = qs('#embeddingBackend')?.value || DEFAULTS.embedding_backend;

        this.state = { service_id, profile_id, model, temperature, top_p, top_k, max_tokens, embedding_backend };
        Storage.save(this.storageKey, this.state);
        this.onSave?.(this.state);

        // push profile change to backend if selected
        if (service_id && profile_id) {
            try {
                await updateLLMService(service_id, { profile_id });
            } catch (err) {
                console.warn('Failed to update LLM service on backend', err);
            }
        }

        // Update embedding backend
        try {
            const response = await fetch('/api/embedding/backend', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ backend: embedding_backend })
            });
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to update embedding backend');
            }
            const data = await response.json();
            this.updateEmbeddingStatus(data);
            alert(`Embedding backend updated to ${embedding_backend}. ${data.message || ''}`);
        } catch (err) {
            console.error('Failed to update embedding backend', err);
            alert(`Error updating embedding backend: ${err.message}`);
        }

        this.hide();
    }
}

