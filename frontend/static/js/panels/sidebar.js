import { qs, on, toggleClass } from '../ui/domUtils.js';
import { Storage } from '../ui/storage.js';

export class SidebarPanel {
    constructor(eventBus, listView, graphView, onViewChange) {
        this.eventBus = eventBus;
        this.listView = listView;
        this.graphView = graphView;
        this.viewMode = 'list';
        this.onViewChange = onViewChange;
    }

    init() {
        on(qs('#viewList'), 'click', () => {
            this.viewMode = 'list';
            this.onViewChange?.('list');
            this.updateViewMode();
        });
        on(qs('#viewGraph'), 'click', () => {
            this.viewMode = 'graph';
            this.onViewChange?.('graph');
            this.updateViewMode();
        });

        // Restore panel state
        const minimized = Storage.load('panelSidebarMinimized', false);
        if (minimized) {
            qs('.sidebar')?.classList.add('minimized');
            qs('[data-panel="sidebar"]')?.classList.add('minimized');
        }
    }

    render(stories) {
        if (this.viewMode === 'list') {
            this.graphView.removeControls?.();
            this.listView.render(stories);
            if (this.listView.currentStoryId) {
                this.listView.updateSelection();
            }
        } else {
            this.graphView.render(stories);
        }
    }

    updateViewMode() {
        toggleClass(qs('#viewList'), 'active', this.viewMode === 'list');
        toggleClass(qs('#viewGraph'), 'active', this.viewMode === 'graph');
        this.render(this.listView.stories);
    }
}

