// SDASystem Frontend Application
const API_BASE = '/api';

class SDAApp {
    constructor() {
        this.stories = [];
        this.currentStory = null;
        this.currentNews = null;
        this.currentActor = null;
        this.viewMode = 'list'; // 'list' or 'graph'

        this.init();
    }

    async init() {
        console.log('Initializing SDASystem...');
        await this.loadData();
        this.setupEventListeners();
        this.updateStats();
        this.renderStories();
    }

    async loadData() {
        try {
            showLoading('sidebar');
            const response = await fetch(`${API_BASE}/stories?sort_by=relevance&limit=100`);
            this.stories = await response.json();
            console.log(`Loaded ${this.stories.length} stories`);
            hideLoading('sidebar');
        } catch (error) {
            console.error('Failed to load stories:', error);
            showError('sidebar', 'Failed to load stories');
        }
    }

    setupEventListeners() {
        // View mode toggle
        document.getElementById('viewList').addEventListener('click', () => {
            this.viewMode = 'list';
            this.updateViewMode();
        });

        document.getElementById('viewGraph').addEventListener('click', () => {
            this.viewMode = 'graph';
            this.updateViewMode();
        });

        // Timeline controls
        document.getElementById('zoomDay').addEventListener('click', () => this.setTimelineZoom('day'));
        document.getElementById('zoomWeek').addEventListener('click', () => this.setTimelineZoom('week'));
        document.getElementById('zoomMonth').addEventListener('click', () => this.setTimelineZoom('month'));
    }

    updateViewMode() {
        document.getElementById('viewList').classList.toggle('active', this.viewMode === 'list');
        document.getElementById('viewGraph').classList.toggle('active', this.viewMode === 'graph');

        if (this.viewMode === 'list') {
            this.renderStories();
        } else {
            this.renderGraph();
        }
    }

    renderStories() {
        const container = document.getElementById('storiesList');
        container.innerHTML = '';

        if (this.stories.length === 0) {
            container.innerHTML = '<div class="loading">No stories found</div>';
            return;
        }

        this.stories.forEach(story => {
            const item = this.createStoryItem(story);
            container.appendChild(item);
        });

        // Select first story
        if (this.stories.length > 0 && !this.currentStory) {
            this.selectStory(this.stories[0].id);
        }
    }

    createStoryItem(story) {
        const div = document.createElement('div');
        div.className = 'story-item';
        if (this.currentStory && this.currentStory.id === story.id) {
            div.classList.add('active');
        }

        div.innerHTML = `
            <h3>${escapeHtml(story.title)}</h3>
            <div class="story-meta">
                <span>${story.size} news</span>
                <span>${story.top_actors.length} actors</span>
                <span>${formatDate(story.last_activity)}</span>
            </div>
            <div class="story-metrics">
                <span class="metric">R: ${(story.relevance * 100).toFixed(0)}%</span>
                <span class="metric">F: ${(story.freshness * 100).toFixed(0)}%</span>
                <span class="metric">C: ${(story.cohesion * 100).toFixed(0)}%</span>
            </div>
        `;

        div.addEventListener('click', () => this.selectStory(story.id));
        return div;
    }

    async selectStory(storyId) {
        try {
            // Fetch full story details
            const response = await fetch(`${API_BASE}/stories/${storyId}`);
            this.currentStory = await response.json();

            // Update UI
            this.renderStoryDetail();
            this.loadStoryEvents(storyId);
            this.updateStorySelection();
            this.clearDetailPanel();
        } catch (error) {
            console.error('Failed to load story:', error);
        }
    }

    async renderStoryDetail() {
        const container = document.getElementById('mainPanel');
        const story = this.currentStory;

        if (!story) {
            container.innerHTML = '<div class="loading">Select a story to view details</div>';
            return;
        }

        // Fetch news for this story
        const newsResponse = await fetch(`${API_BASE}/news?story_id=${story.id}`);
        const newsItems = await newsResponse.json();

        // Fetch actors
        const actorsHtml = await this.renderActorsSection(story.top_actors);

        container.innerHTML = `
            <div class="story-detail">
                <h1>${escapeHtml(story.title)}</h1>
                <div class="meta-info">
                    <span>${story.size} news items</span>
                    <span>${story.top_actors.length} actors</span>
                    <span>Updated ${formatDate(story.last_activity)}</span>
                    <span>${story.primary_domain || 'N/A'}</span>
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

        // Add event listeners to news items
        document.querySelectorAll('.news-item').forEach(item => {
            item.addEventListener('click', () => {
                const newsId = item.dataset.newsId;
                this.selectNews(newsId);
            });
        });

        // Add event listeners to actor chips
        document.querySelectorAll('.actor-chip').forEach(chip => {
            chip.addEventListener('click', () => {
                const actorId = chip.dataset.actorId;
                this.selectActor(actorId);
            });
        });
    }

    async renderActorsSection(actorIds) {
        if (actorIds.length === 0) return '<p>No actors identified</p>';

        const actorsHtml = [];
        for (const actorId of actorIds.slice(0, 12)) { // Limit to 12
            try {
                const response = await fetch(`${API_BASE}/actors/${actorId}`);
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

    async selectNews(newsId) {
        try {
            const response = await fetch(`${API_BASE}/news/${newsId}`);
            this.currentNews = await response.json();
            this.renderNewsDetail();
        } catch (error) {
            console.error('Failed to load news:', error);
        }
    }

    async renderNewsDetail() {
        const container = document.getElementById('detailPanel');
        const news = this.currentNews;

        if (!news) return;

        // Fetch actors mentioned in this news
        let actorsHtml = '';
        if (news.mentioned_actors && news.mentioned_actors.length > 0) {
            const actorsList = [];
            for (const actorId of news.mentioned_actors.slice(0, 10)) {
                try {
                    const response = await fetch(`${API_BASE}/actors/${actorId}`);
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

        container.innerHTML = `
            <div class="news-detail">
                <h2>News Details</h2>
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

        // Add event listeners to actor chips
        document.querySelectorAll('.actor-chip').forEach(chip => {
            chip.addEventListener('click', () => {
                const actorId = chip.dataset.actorId;
                this.selectActor(actorId);
            });
        });
    }

    async selectActor(actorId) {
        try {
            const response = await fetch(`${API_BASE}/actors/${actorId}`);
            this.currentActor = await response.json();
            this.renderActorDetail();
        } catch (error) {
            console.error('Failed to load actor:', error);
        }
    }

    async renderActorDetail() {
        const container = document.getElementById('detailPanel');
        const actor = this.currentActor;

        if (!actor) return;

        // Fetch mentions
        const mentionsResponse = await fetch(`${API_BASE}/actors/${actor.id}/mentions?limit=10`);
        const mentions = await mentionsResponse.json();

        const aliasesHtml = actor.aliases && actor.aliases.length > 0
            ? actor.aliases.map(a => `<span class="alias-tag">${escapeHtml(a.name)}</span>`).join('')
            : '<span class="alias-tag">No aliases</span>';

        container.innerHTML = `
            <div class="actor-detail">
                <h2>Actor Details</h2>
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

        // Add event listeners to news items
        document.querySelectorAll('.news-item').forEach(item => {
            item.addEventListener('click', () => {
                const newsId = item.dataset.newsId;
                this.selectNews(newsId);
            });
        });
    }

    clearDetailPanel() {
        const container = document.getElementById('detailPanel');
        container.innerHTML = `
            <div class="empty-state">
                <p>Select a news item or actor to view details</p>
            </div>
        `;
    }

    async loadStoryEvents(storyId) {
        try {
            const response = await fetch(`${API_BASE}/stories/${storyId}/events`);
            const events = await response.json();
            this.renderTimeline(events);
        } catch (error) {
            console.error('Failed to load events:', error);
            this.renderTimeline([]);
        }
    }

    renderTimeline(events) {
        const container = document.getElementById('timelineEvents');

        if (events.length === 0) {
            container.innerHTML = '<div class="loading">No timeline events for this story</div>';
            return;
        }

        // Sort by date
        events.sort((a, b) => new Date(a.event_date) - new Date(b.event_date));

        container.innerHTML = events.map(event => `
            <div class="event-item ${event.event_type}">
                <div class="event-date">${formatDate(event.event_date)}</div>
                <div class="event-title">${escapeHtml(event.title)}</div>
                <div class="event-description">${escapeHtml(event.description.substring(0, 100))}...</div>
                <span class="event-type-badge ${event.event_type}">
                    ${event.event_type === 'fact' ? 'FACT' : 'OPINION'}
                </span>
            </div>
        `).join('');
    }

    updateStorySelection() {
        document.querySelectorAll('.story-item').forEach(item => {
            item.classList.remove('active');
        });

        if (this.currentStory) {
            const currentItem = Array.from(document.querySelectorAll('.story-item'))
                .find(item => item.querySelector('h3').textContent === this.currentStory.title);
            if (currentItem) {
                currentItem.classList.add('active');
            }
        }
    }

    async updateStats() {
        try {
            const response = await fetch(`${API_BASE}/stats`);
            const stats = await response.json();

            document.getElementById('statsStories').textContent = stats.stories_count || 0;
            document.getElementById('statsNews').textContent = stats.news_count || 0;
            document.getElementById('statsActors').textContent = stats.actors_count || 0;
        } catch (error) {
            console.error('Failed to load stats:', error);
        }
    }

    setTimelineZoom(level) {
        console.log(`Timeline zoom: ${level}`);
        // Implement timeline zoom logic
    }

    renderGraph() {
        const container = document.getElementById('storiesList');
        container.innerHTML = '<div class="loading">Graph view coming soon...</div>';
    }
}

// Utility functions
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDate(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;

    return date.toLocaleDateString();
}

function showLoading(containerId) {
    const container = document.getElementById(containerId);
    if (container) {
        container.innerHTML = '<div class="loading"><div class="spinner"></div>Loading...</div>';
    }
}

function hideLoading(containerId) {
    // Loading will be replaced by content
}

function showError(containerId, message) {
    const container = document.getElementById(containerId);
    if (container) {
        container.innerHTML = `<div class="loading" style="color: #f44336;">${message}</div>`;
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.sdaApp = new SDAApp();
});
