/**
 * Panel Resizer - Handles resizable panels with drag functionality
 */
class PanelResizer {
    constructor() {
        this.isResizing = false;
        this.currentResizer = null;
        this.startX = 0;
        this.startWidth = 0;
        this.minWidth = 200;
        this.maxWidthPercent = 0.6; // Maximum 60% of container width

        this.init();
    }

    init() {
        console.log('PanelResizer initialized');
        const resizers = document.querySelectorAll('.resizer-vertical');

        resizers.forEach(resizer => {
            resizer.addEventListener('mousedown', (e) => this.startResize(e, resizer));
        });

        document.addEventListener('mousemove', (e) => this.resize(e));
        document.addEventListener('mouseup', () => this.stopResize());
    }

    startResize(e, resizer) {
        this.isResizing = true;
        this.currentResizer = resizer;
        this.startX = e.clientX;

        const target = resizer.dataset.target;
        const container = document.querySelector('.app-container');

        if (target === 'sidebar') {
            const sidebar = document.querySelector('.sidebar');
            this.startWidth = sidebar.offsetWidth;
            this.targetElement = sidebar;
            this.cssVariable = '--sidebar-width';
        } else if (target === 'main') {
            const detail = document.querySelector('.detail-panel');
            this.startWidth = detail.offsetWidth;
            this.targetElement = detail;
            this.cssVariable = '--detail-width';
        }

        resizer.classList.add('resizing');
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';

        e.preventDefault();
    }

    resize(e) {
        if (!this.isResizing || !this.currentResizer) return;

        const container = document.querySelector('.app-container');
        const containerWidth = container.offsetWidth;
        const maxWidth = containerWidth * this.maxWidthPercent;

        let newWidth;

        if (this.currentResizer.dataset.target === 'sidebar') {
            // Sidebar resizes from left to right
            const delta = e.clientX - this.startX;
            newWidth = this.startWidth + delta;
        } else {
            // Detail panel resizes from right to left
            const delta = this.startX - e.clientX;
            newWidth = this.startWidth + delta;
        }

        // Constrain width
        newWidth = Math.max(this.minWidth, Math.min(newWidth, maxWidth));

        // Update CSS variable
        container.style.setProperty(this.cssVariable, `${newWidth}px`);
    }

    stopResize() {
        if (!this.isResizing) return;

        this.isResizing = false;

        if (this.currentResizer) {
            this.currentResizer.classList.remove('resizing');
            this.currentResizer = null;
        }

        document.body.style.cursor = '';
        document.body.style.userSelect = '';
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new PanelResizer();
});
