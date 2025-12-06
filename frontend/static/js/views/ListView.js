/**
 * ListView - Renders stories as a list in the left sidebar
 */
export class ListView {
    constructor(containerId, eventBus) {
        this.container = document.getElementById(containerId);
        this.eventBus = eventBus;
        this.stories = [];
        this.currentStoryId = null;
    }

    /**
     * Render the list of stories
     * @param {Array} stories - Array of story objects
     */
    render(stories) {
        this.stories = stories;
        this.container.innerHTML = '';

        if (stories.length === 0) {
            this.container.innerHTML = '<div class="loading">No stories found</div>';
            return;
        }

        stories.forEach(story => {
            const item = this.createStoryItem(story);
            this.container.appendChild(item);
        });
    }

    /**
     * Create HTML element for a single story
     * @param {Object} story - Story object
     * @returns {HTMLElement} Story item element
     */
    createStoryItem(story) {
        const div = document.createElement('div');
        div.className = 'story-item';
        div.dataset.storyId = story.id;

        if (this.currentStoryId === story.id) {
            div.classList.add('active');
        }

        div.innerHTML = `
            <h3>${escapeHtml(story.title)}</h3>
            <div class="story-meta">
                <span>${story.size} news</span>
                <span>${story.top_actors.length} actors</span>
                <span>${formatDate(story.last_activity)}</span>
                <span>${escapeHtml(this.getPrimaryDomain(story) || 'No domain')}</span>
            </div>
            <div class="story-metrics">
                <span class="metric">R: ${(story.relevance * 100).toFixed(0)}%</span>
                <span class="metric">F: ${(story.freshness * 100).toFixed(0)}%</span>
                <span class="metric">C: ${(story.cohesion * 100).toFixed(0)}%</span>
            </div>
        `;

        div.addEventListener('click', () => {
            this.selectStory(story.id);
        });

        return div;
    }

    /**
     * Select a story and emit event
     * @param {string} storyId - Story ID
     */
    selectStory(storyId) {
        this.currentStoryId = storyId;
        this.updateSelection();
        this.eventBus.emit('story:selected', storyId);
    }

    /**
     * Update visual selection state
     */
    updateSelection() {
        this.container.querySelectorAll('.story-item').forEach(item => {
            item.classList.remove('active');
            if (item.dataset.storyId === this.currentStoryId) {
                item.classList.add('active');
            }
        });
    }

    /**
     * Resolve primary domain label
     */
    getPrimaryDomain(story) {
        if (story.primary_domain) return story.primary_domain.replace('domain_', '').replace(/_/g, ' ');
        if (story.domains && story.domains.length > 0) return story.domains[0].replace('domain_', '').replace(/_/g, ' ');
        return '';
    }

    /**
     * Clear the list
     */
    clear() {
        this.container.innerHTML = '';
        this.stories = [];
        this.currentStoryId = null;
    }

    /**
     * Show loading state
     */
    showLoading() {
        this.container.innerHTML = '<div class="loading"><div class="spinner"></div>Loading stories...</div>';
    }
}
