/**
 * StoryView - Renders detailed story information in the main panel
 */
export class StoryView {
    constructor(containerId, eventBus, apiBase) {
        this.container = document.querySelector(containerId);
        this.eventBus = eventBus;
        this.apiBase = apiBase;
        this.currentStory = null;
    }

    /**
     * Render story details
     * @param {Object} story - Story object
     */
    async render(story) {
        this.currentStory = story;

        if (!story) {
            this.container.innerHTML = '<div class="loading">Select a story to view details</div>';
            return;
        }

        try {
            // Fetch news for this story
            const newsResponse = await fetch(`${this.apiBase}/news?story_id=${story.id}`);
            const newsItems = await newsResponse.json();

            // Fetch actors
            const actorsHtml = await this.renderActorsSection(story.top_actors);

            this.container.innerHTML = `
                <div class="story-detail">
                    <h1>${escapeHtml(story.title)}</h1>
                    <div class="meta-info">
                        <span>${story.size} news items</span>
                        <span>${story.top_actors.length} actors</span>
                        <span>Updated ${formatDate(story.last_activity)}</span>
                        <span>${this.formatDomain(story.primary_domain) || 'N/A'}</span>
                    </div>
                    <div class="meta-info">
                        <span>Relevance: ${(story.relevance * 100).toFixed(0)}%</span>
                        <span>Cohesion: ${(story.cohesion * 100).toFixed(0)}%</span>
                        <span>Freshness: ${(story.freshness * 100).toFixed(0)}%</span>
                    </div>
                    <div class="meta-info">
                        ${(story.domains && story.domains.length)
                            ? story.domains.map(d => `<span>${escapeHtml(this.formatDomain(d))}</span>`).join('')
                            : '<span>No domains</span>'}
                    </div>
                    <div class="summary">
                        ${escapeHtml(story.summary)}
                    </div>

                    <h2 class="section-title">Key Points</h2>
                    <ul class="bullets-list">
                        ${story.bullets.map(b => `<li>${escapeHtml(b)}</li>`).join('')}
                    </ul>

                    <h2 class="section-title">Top Actors</h2>
                    <div class="actors-grid">
                        ${actorsHtml}
                    </div>

                    <h2 class="section-title">Related News (${newsItems.length})</h2>
                    <div class="news-list">
                        ${newsItems.map(n => this.createNewsItemHtml(n)).join('')}
                    </div>
                </div>
            `;

            this.setupEventListeners();
        } catch (error) {
            console.error('Error rendering story:', error);
            this.container.innerHTML = '<div class="error">Failed to load story details</div>';
        }
    }

    /**
     * Render actors section
     * @param {Array} actorIds - Array of actor IDs
     * @returns {string} HTML string
     */
    async renderActorsSection(actorIds) {
        if (actorIds.length === 0) return '<p>No actors identified</p>';

        const actorsHtml = [];
        for (const actorId of actorIds.slice(0, 12)) { // Limit to 12
            try {
                const response = await fetch(`${this.apiBase}/actors/${actorId}`);
                const actor = await response.json();
                actorsHtml.push(`
                    <div class="actor-chip" data-actor-id="${actor.id}">
                        ${escapeHtml(actor.canonical_name)}
                    </div>
                `);
            } catch (error) {
                console.warn(`Failed to load actor ${actorId}`);
            }
        }

        return actorsHtml.join('');
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
     * Setup event listeners for interactive elements
     */
    setupEventListeners() {
        // News item clicks
        this.container.querySelectorAll('.news-item').forEach(item => {
            item.addEventListener('click', () => {
                const newsId = item.dataset.newsId;
                this.eventBus.emit('news:selected', newsId);
            });
        });

        // Actor chip clicks
        this.container.querySelectorAll('.actor-chip').forEach(chip => {
            chip.addEventListener('click', () => {
                const actorId = chip.dataset.actorId;
                this.eventBus.emit('actor:selected', actorId);
            });
        });
    }

    /**
     * Clear the view
     */
    clear() {
        this.container.innerHTML = '';
        this.currentStory = null;
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
     * Show loading state
     */
    showLoading() {
        this.container.innerHTML = '<div class="loading"><div class="spinner"></div>Loading story details...</div>';
    }
}
