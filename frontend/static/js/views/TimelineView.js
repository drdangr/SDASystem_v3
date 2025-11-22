/**
 * TimelineView - Renders timeline of events in the bottom panel
 */
class TimelineView {
    constructor(containerId, eventBus, apiBase) {
        this.container = document.getElementById(containerId);
        this.eventBus = eventBus;
        this.apiBase = apiBase;
        this.events = [];
        this.zoomLevel = 'week';
    }

    /**
     * Load and render timeline for a story
     * @param {string} storyId - Story ID
     */
    async loadStoryTimeline(storyId) {
        if (!storyId) {
            this.clear();
            return;
        }

        try {
            const response = await fetch(`${this.apiBase}/stories/${storyId}/events`);
            const events = await response.json();
            this.render(events);
        } catch (error) {
            console.error('Error loading timeline:', error);
            this.container.innerHTML = '<div class="loading">Failed to load timeline</div>';
        }
    }

    /**
     * Render timeline events
     * @param {Array} events - Array of event objects
     */
    render(events) {
        this.events = events;

        if (events.length === 0) {
            this.container.innerHTML = '<div class="loading">No events in timeline</div>';
            return;
        }

        const eventsHtml = events.map(event => `
            <div class="event-item ${event.type || 'fact'}">
                <div class="event-date">${formatDate(event.timestamp)}</div>
                <div class="event-title">${escapeHtml(event.title)}</div>
                <div class="event-description">${escapeHtml(event.description || '')}</div>
            </div>
        `).join('');

        this.container.innerHTML = `
            <div class="timeline-events-container">
                ${eventsHtml}
            </div>
        `;
    }

    /**
     * Set timeline zoom level
     * @param {string} level - Zoom level: 'day', 'week', 'month'
     */
    setZoom(level) {
        this.zoomLevel = level;
        console.log(`Timeline zoom set to: ${level}`);
        // TODO: Implement zoom logic to filter/group events
        this.render(this.events);
    }

    /**
     * Clear the timeline
     */
    clear() {
        this.container.innerHTML = '<div class="loading">Select a story to view timeline</div>';
        this.events = [];
    }

    /**
     * Show loading state
     */
    showLoading() {
        this.container.innerHTML = '<div class="loading"><div class="spinner"></div>Loading timeline...</div>';
    }
}
