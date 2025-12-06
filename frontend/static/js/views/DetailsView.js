/**
 * DetailsView - Renders detailed information for selected news or actor in the right panel
 */
import { Storage } from '../ui/storage.js';

export class DetailsView {
    constructor(containerId, eventBus, apiBase) {
        this.container = document.querySelector(containerId);
        this.eventBus = eventBus;
        this.apiBase = apiBase;
        this.currentNews = null;
        this.currentActor = null;
    }

    /**
     * Render news detail
     * @param {Object} news - News object
     */
    async renderNews(news, actorsOverride = null, actorIdsOverride = null) {
        this.currentNews = news;
        this.currentActor = null;

        if (!news) return;

        try {
            // Fetch actors mentioned in this news
            let actorsHtml = '';
            const ids = actorIdsOverride
                ? actorIdsOverride
                : (news.mentioned_actors || []).filter(id => typeof id === 'string' && id.startsWith('actor_'));
            const actorsList = [];
            if (Array.isArray(actorsOverride) && actorsOverride.length > 0) {
                for (const a of actorsOverride) {
                    actorsList.push(`
                        <div class="actor-chip">
                            ${escapeHtml(a.name || '')}
                        </div>
                    `);
                }
            } else if (ids.length > 0) {
                for (const actorId of ids.slice(0, 10)) {
                    try {
                        const response = await fetch(`${this.apiBase}/actors/${actorId}`);
                        if (!response.ok) throw new Error(`HTTP ${response.status}`);
                        const actor = await response.json();
                        actorsList.push(`
                            <div class="actor-chip" data-actor-id="${actor.id}">
                                ${escapeHtml(actor.canonical_name)}
                            </div>
                        `);
                    } catch (error) {
                        console.warn(`Failed to load actor ${actorId}`, error);
                    }
                }
            }
            actorsHtml = actorsList.join('');

            this.container.innerHTML = `
                <div class="news-detail">
                    <h3 style="font-size: 18px; color: #fff; margin: 15px 0;">${escapeHtml(news.title)}</h3>

                    <div class="llm-status-line">
                        <span class="llm-label">LLM actors:</span>
                        <span class="llm-status" id="llmActorsStatus"></span>
                        <button class="llm-btn" id="llmActorsRefresh">Refresh</button>
                    </div>

                    <div class="detail-section">
                        <h3>Source</h3>
                        <p>${escapeHtml(news.source)}</p>
                    </div>

                    <div class="detail-section">
                        <h3>Published</h3>
                        <p>${formatDate(news.published_at)}</p>
                    </div>

                    <div class="detail-section">
                        <h3>Summary</h3>
                        <p style="line-height: 1.6;">${escapeHtml(news.summary)}</p>
                    </div>

                    ${news.full_text ? `
                        <div class="detail-section">
                            <h3>Full Text</h3>
                            <p style="line-height: 1.6;">${escapeHtml(news.full_text)}</p>
                        </div>
                    ` : ''}

                    <div class="detail-section">
                        <h3>Mentioned Actors</h3>
                        <div class="actors-grid">
                            ${actorsHtml || '<span class="alias-tag">No actors</span>'}
                        </div>
                    </div>

                    ${news.domains && news.domains.length > 0 ? `
                        <div class="detail-section">
                            <h3>Domains</h3>
                            <div class="aliases-list">
                                ${news.domains.map(d => `<span class="alias-tag">${escapeHtml(this.formatDomain(d))}</span>`).join('')}
                            </div>
                        </div>
                    ` : ''}
                </div>
            `;

            this.setupEventListeners();
            this.setupActorsRefresh(news.id);
        } catch (error) {
            console.error('Error rendering news detail:', error);
            this.container.innerHTML = '<div class="error">Failed to load news details</div>';
        }
    }

    /**
     * Render actor detail
     * @param {Object} actor - Actor object
     */
    async renderActor(actor) {
        this.currentActor = actor;
        this.currentNews = null;

        if (!actor) return;

        try {
            // Fetch mentions
            const mentionsResponse = await fetch(`${this.apiBase}/actors/${actor.id}/mentions?limit=10`);
            const mentions = await mentionsResponse.json();

            const aliasesHtml = actor.aliases && actor.aliases.length > 0
                ? actor.aliases.map(a => `<span class="alias-tag">${escapeHtml(a.name)}</span>`).join('')
                : '<span class="alias-tag">No aliases</span>';

            this.container.innerHTML = `
                <div class="actor-detail">
                    <div class="actor-name">${escapeHtml(actor.canonical_name)}</div>
                    <span class="actor-type">${escapeHtml(actor.actor_type)}</span>

                    <div class="detail-section">
                        <h3>Aliases</h3>
                        <div class="aliases-list">
                            ${aliasesHtml}
                        </div>
                    </div>

                    <div class="detail-section">
                        <h3>Recent Mentions (${mentions.length})</h3>
                        <div class="news-list" style="max-height: 400px; overflow-y: auto;">
                            ${mentions.map(n => this.createNewsItemHtml(n)).join('')}
                        </div>
                    </div>
                </div>
            `;

            this.setupEventListeners();
        } catch (error) {
            console.error('Error rendering actor detail:', error);
            this.container.innerHTML = '<div class="error">Failed to load actor details</div>';
        }
    }

    /**
     * Create HTML for a news item
     * @param {Object} news - News object
     * @returns {string} HTML string
     */
    createNewsItemHtml(news) {
        return `
            <div class="news-item" data-news-id="${news.id}">
                <h4>${escapeHtml(news.title)}</h4>
                <p>${escapeHtml(news.summary)}</p>
                <div class="news-meta">
                    <span>${news.source}</span> •
                    <span>${formatDate(news.published_at)}</span>
                </div>
            </div>
        `;
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Actor chip clicks
        this.container.querySelectorAll('.actor-chip').forEach(chip => {
            chip.addEventListener('click', () => {
                const actorId = chip.dataset.actorId;
                this.eventBus.emit('actor:selected', actorId);
            });
        });

        // News item clicks
        this.container.querySelectorAll('.news-item').forEach(item => {
            item.addEventListener('click', () => {
                const newsId = item.dataset.newsId;
                this.eventBus.emit('news:selected', newsId);
            });
        });
    }

    setupActorsRefresh(newsId) {
        const btn = this.container.querySelector('#llmActorsRefresh');
        const statusEl = this.container.querySelector('#llmActorsStatus');
        // preserve reference to current news for update
        const currentNews = this.currentNews;
        if (!btn) return;

        btn.addEventListener('click', async () => {
            try {
                if (statusEl) statusEl.textContent = 'Loading...';
                const settings = Storage.load('llmSettings', null) || {};
                const payload = {
                    news_id: newsId,
                    model: settings.model,
                    temperature: settings.temperature,
                    top_p: settings.top_p,
                    top_k: settings.top_k,
                    max_tokens: settings.max_tokens
                };
                const resp = await fetch(`/api/news/${newsId}/actors/refresh`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                if (!resp.ok) {
                    const txt = await resp.text();
                    window.lastLLMDebug = `HTTP ${resp.status}: ${txt}`;
                    throw new Error(`HTTP ${resp.status}`);
                }
                const data = await resp.json();
                console.log('LLM actors response', data);
                const debugObj = {
                    actors: data.actors,
                    actor_ids: data.actor_ids,
                    raw: data.raw
                };
                window.lastLLMDebug = JSON.stringify(debugObj, null, 2);

                // render actors directly from response
                const actorsList = Array.isArray(data.actors) ? data.actors : [];
                // re-render with overrides
                await this.renderNews({
                    ...currentNews,
                    mentioned_actors: data.actor_ids || currentNews?.mentioned_actors || []
                }, actorsList, data.actor_ids);

                // notify app to refresh stories/graph aggregates
                this.eventBus.emit('actors:updated');

                // re-fetch news to sync with backend, but ensure mentioned_actors are kept
                const newsResp = await fetch(`/api/news/${newsId}`);
                const updated = await newsResp.json();
                if (data.actor_ids && Array.isArray(data.actor_ids)) {
                    updated.mentioned_actors = data.actor_ids;
                }
                await this.renderNews(updated, actorsList, data.actor_ids);
                if (statusEl) statusEl.textContent = 'Done';
            } catch (e) {
                console.error('LLM actors refresh error', e);
                window.lastLLMDebug = String(e);
                if (statusEl) statusEl.textContent = 'Error';
            }
        });
    }

    /**
     * Format domain ID to readable name
     * @param {string} domainId 
     * @returns {string}
     */
    formatDomain(domainId) {
        if (!domainId) return '';
        // domain_united_states -> United States
        return domainId.replace('domain_', '').split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
    }

    /**
     * Clear the detail panel
     */
    clear() {
        this.container.innerHTML = `
            <div class="empty-state">
                <p>Select a news item or actor to view details</p>
            </div>
        `;
        this.currentNews = null;
        this.currentActor = null;
    }
}
