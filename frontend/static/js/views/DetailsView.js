/**
 * DetailsView - Renders detailed information for selected news or actor in the right panel
 */
class DetailsView {
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
    async renderNews(news) {
        this.currentNews = news;
        this.currentActor = null;

        if (!news) return;

        try {
            // Fetch actors mentioned in this news
            let actorsHtml = '';
            if (news.mentioned_actors && news.mentioned_actors.length > 0) {
                const actorsList = [];
                for (const actorId of news.mentioned_actors.slice(0, 10)) {
                    try {
                        const response = await fetch(`${this.apiBase}/actors/${actorId}`);
                        const actor = await response.json();
                        actorsList.push(`
                            <div class="actor-chip" data-actor-id="${actor.id}">
                                ${escapeHtml(actor.canonical_name)}
                            </div>
                        `);
                    } catch (error) {
                        console.warn(`Failed to load actor ${actorId}`);
                    }
                }
                actorsHtml = actorsList.join('');
            }

            this.container.innerHTML = `
                <div class="news-detail">
                    <h3 style="font-size: 18px; color: #fff; margin: 15px 0;">${escapeHtml(news.title)}</h3>

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

                    ${news.mentioned_actors && news.mentioned_actors.length > 0 ? `
                        <div class="detail-section">
                            <h3>Mentioned Actors</h3>
                            <div class="actors-grid">
                                ${actorsHtml}
                            </div>
                        </div>
                    ` : ''}

                    ${news.domains && news.domains.length > 0 ? `
                        <div class="detail-section">
                            <h3>Domains</h3>
                            <div class="aliases-list">
                                ${news.domains.map(d => `<span class="alias-tag">${escapeHtml(d)}</span>`).join('')}
                            </div>
                        </div>
                    ` : ''}
                </div>
            `;

            this.setupEventListeners();
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
