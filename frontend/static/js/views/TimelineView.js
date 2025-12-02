/**
 * TimelineView - Renders timeline of events in the bottom panel
 */
class TimelineView {
    constructor(containerSelector, eventBus, apiBase) {
        // Поддерживаем как ID, так и селектор класса
        this.container = containerSelector.startsWith('.') 
            ? document.querySelector(containerSelector)
            : document.getElementById(containerSelector);
        if (!this.container) {
            console.warn(`TimelineView: Container '${containerSelector}' not found`);
        }
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
        if (!this.container) {
            console.error('TimelineView: Container not found');
            return;
        }
        if (!storyId) {
            this.clear();
            return;
        }

        // Показываем состояние загрузки
        this.showLoading();

        try {
            const response = await fetch(`${this.apiBase}/stories/${storyId}/events`);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const events = await response.json();
            this.render(events);
        } catch (error) {
            console.error('Error loading timeline:', error);
            if (this.container) {
                this.container.innerHTML = `<div class="loading">Failed to load timeline: ${error.message}</div>`;
            }
        }
    }

    /**
     * Render timeline events
     * @param {Array} events - Array of event objects
     */
    render(events) {
        if (!this.container) return;
        this.events = events;

        if (events.length === 0) {
            this.container.innerHTML = '<div class="loading">No events in timeline</div>';
            return;
        }

        const eventsHtml = events.map(event => `
            <div class="event-item ${event.event_type || event.type || 'fact'}">
                <div class="event-date">${formatDate(event.event_date || event.timestamp)}</div>
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
        if (this.container) this.container.innerHTML = '<div class="loading">Select a story to view timeline</div>';
        this.events = [];
    }

    /**
     * Show loading state
     */
    showLoading() {
        if (this.container) this.container.innerHTML = '<div class="loading"><div class="spinner"></div>Loading timeline...</div>';
    }
}
