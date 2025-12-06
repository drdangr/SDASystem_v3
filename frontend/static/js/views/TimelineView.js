/**
 * TimelineView - Renders timeline of events in the bottom panel
 */
export class TimelineView {
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
        this.zoomLevel = 'month';
        this.expandedEventId = null;
        this.filters = { fact: true, opinion: true };
        this.zoomScale = 1.0; // 1 = fit, <1 zoom in, >1 zoom out
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
        this.events = (events || []).slice();

        if (this.events.length === 0) {
            this.container.innerHTML = '<div class="loading">No events in timeline</div>';
            return;
        }

        // Фильтр по типу
        const filtered = this.events.filter(ev => {
            const t = (ev.event_type || ev.type || 'fact').toLowerCase();
            return (t === 'fact' && this.filters.fact) || (t === 'opinion' && this.filters.opinion) || (!['fact', 'opinion'].includes(t));
        });
        if (filtered.length === 0) {
            this.container.innerHTML = '<div class="loading">No events for selected filters</div>';
            return;
        }

        // Sort by date
        filtered.sort((a, b) => {
            const da = new Date(a.event_date || a.timestamp).getTime();
            const db = new Date(b.event_date || b.timestamp).getTime();
            return da - db;
        });

        const minTime = new Date(filtered[0].event_date || filtered[0].timestamp).getTime();
        const maxTime = new Date(filtered[filtered.length - 1].event_date || filtered[filtered.length - 1].timestamp).getTime();
        const span = Math.max(1, maxTime - minTime);

        // Adjust span by zoomScale around center
        const mid = (minTime + maxTime) / 2;
        const half = (span / 2) * this.zoomScale;
        const adjMin = mid - half;
        const adjMax = mid + half;
        const adjSpan = Math.max(1, adjMax - adjMin);

        const pinsHtml = filtered.map((ev) => {
            const cls = ev.event_type || ev.type || 'fact';
            const id = ev.id;
            const dateLabel = formatDate(ev.event_date || ev.timestamp);
            const titleLabel = escapeHtml(ev.title || '').substring(0, 40) || 'No title';
            const tooltip = `${dateLabel} • ${titleLabel}`;
            const isExpanded = this.expandedEventId === id;
            const t = new Date(ev.event_date || ev.timestamp).getTime();
            const pct = (filtered.length === 1 && adjSpan === 1)
                ? 50
                : ((t - adjMin) / adjSpan) * 100;
            const pctClamped = Math.min(100, Math.max(0, pct));

            return `
                <div class="event-pin ${cls}" data-event="${id}" title="${tooltip}" style="left:${pctClamped}%">
                    <div class="pin-label">${titleLabel}</div>
                    <div class="dot"></div>
                    <div class="pin-date">${dateLabel}</div>
                </div>
            `;
        }).join('');

        const detailsHtml = filtered.map(ev => {
            if (this.expandedEventId !== ev.id) return '';
            const cls = ev.event_type || ev.type || 'fact';
            const dateLabel = formatDate(ev.event_date || ev.timestamp);
            return `
                <div class="event-card">
                    <div class="event-card-header">
                        <span>${dateLabel}</span>
                        <button class="collapse-btn" data-event="${ev.id}">−</button>
                    </div>
                    <div class="event-card-body">
                        <div class="event-card-item ${cls}">
                            <div class="event-date">${dateLabel}</div>
                            <div class="event-title">${escapeHtml(ev.title)}</div>
                            <div class="event-description">${escapeHtml(ev.description || '')}</div>
                        </div>
                    </div>
            </div>
            `;
        }).join('');

        this.container.innerHTML = `
            <div class="timeline-wrapper">
                <div class="timeline-track">
                    ${this.renderTicks(adjMin, adjMax, this.zoomLevel)}
                </div>
                <div class="timeline-pins-abs">
                    ${pinsHtml}
                </div>
            </div>
            <div class="timeline-details">
                ${detailsHtml}
            </div>
        `;

        // Attach listeners
        this.container.querySelectorAll('.event-pin').forEach(pin => {
            pin.addEventListener('click', () => {
                const eid = pin.dataset.event;
                this.expandedEventId = (this.expandedEventId === eid) ? null : eid;
                this.render(this.events);
            });
        });

        this.container.querySelectorAll('.collapse-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.expandedEventId = null;
                this.render(this.events);
            });
        });
    }

    /**
     * Set timeline zoom level
     * @param {string} level - Zoom level: 'day', 'month', 'year'
     */
    setZoom(level) {
        this.zoomLevel = level;
        console.log(`Timeline zoom set to: ${level}`);
        this.zoomScale = 1.0; // reset fine scale on mode change
        this.render(this.events);
    }

    zoomIn() {
        this.zoomScale = Math.max(0.2, this.zoomScale * 0.8);
        this.render(this.events);
    }

    zoomOut() {
        this.zoomScale = Math.min(5.0, this.zoomScale * 1.25);
        this.render(this.events);
    }

    toggleFilter(kind) {
        if (kind === 'fact' || kind === 'opinion') {
            this.filters[kind] = !this.filters[kind];
            this.render(this.events);
        }
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

    /**
     * Render ticks on the timeline according to zoom level
     */
    renderTicks(minTime, maxTime, zoomLevel) {
        const ticks = this.buildTicks(minTime, maxTime, zoomLevel);
        return ticks.map(tick => `
            <div class="timeline-tick" style="left:${tick.pct}%">
                <div class="tick-line"></div>
                <div class="tick-label">${tick.label}</div>
            </div>
        `).join('');
    }

    buildTicks(minTime, maxTime, zoomLevel) {
        const ticks = [];
        const span = Math.max(1, maxTime - minTime);

        const pushTick = (time) => {
            const pct = ((time - minTime) / span) * 100;
            ticks.push({
                pct,
                label: this.formatTickLabel(time, zoomLevel)
            });
        };

        const dMin = new Date(minTime);
        const dMax = new Date(maxTime);

        if (zoomLevel === 'day') {
            // every day
            let cur = new Date(dMin.getFullYear(), dMin.getMonth(), dMin.getDate());
            while (cur <= dMax) {
                pushTick(cur.getTime());
                cur.setDate(cur.getDate() + 1);
            }
        } else if (zoomLevel === 'month') {
            let cur = new Date(dMin.getFullYear(), dMin.getMonth(), 1);
            while (cur <= dMax) {
                pushTick(cur.getTime());
                cur.setMonth(cur.getMonth() + 1);
            }
        } else {
            // year
            let cur = new Date(dMin.getFullYear(), 0, 1);
            while (cur <= dMax) {
                pushTick(cur.getTime());
                cur.setFullYear(cur.getFullYear() + 1);
            }
        }

        return ticks;
    }

    formatTickLabel(time, zoomLevel) {
        const d = new Date(time);
        if (zoomLevel === 'day') {
            return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
        }
        if (zoomLevel === 'month') {
            return d.toLocaleDateString(undefined, { month: 'short', year: 'numeric' });
        }
        // year
        return d.getFullYear();
    }
}
