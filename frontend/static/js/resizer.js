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
        console.log('PanelResizer initializing...');
        const resizers = document.querySelectorAll('.resizer-vertical');
        console.log(`Found ${resizers.length} resizers`);

        if (resizers.length === 0) {
            console.warn('No resizers found! Check HTML structure.');
            return;
        }

        resizers.forEach((resizer, index) => {
            const target = resizer.dataset.target;
            console.log(`Resizer ${index + 1}: target="${target}"`);
            resizer.addEventListener('mousedown', (e) => this.startResize(e, resizer));
        });

        document.addEventListener('mousemove', (e) => this.resize(e));
        document.addEventListener('mouseup', () => this.stopResize());
        console.log('PanelResizer initialized successfully');
    }

    startResize(e, resizer) {
        this.isResizing = true;
        this.currentResizer = resizer;
        this.startX = e.clientX;

        const target = resizer.dataset.target;
        const container = document.querySelector('.app-container');

        if (target === 'sidebar') {
            const sidebar = document.querySelector('.sidebar');
            if (!sidebar) {
                console.error('Sidebar element not found');
                this.isResizing = false;
                return;
            }
            this.startWidth = sidebar.offsetWidth;
            this.targetElement = sidebar;
            this.cssVariable = '--sidebar-width';
        } else if (target === 'main') {
            // Ресайзер между main и detail изменяет ширину detail-panel
            const detail = document.querySelector('.detail-panel');
            if (!detail) {
                console.error('Detail panel element not found');
                this.isResizing = false;
                return;
            }
            this.startWidth = detail.offsetWidth;
            this.targetElement = detail;
            this.cssVariable = '--detail-width';
        } else {
            console.error('Unknown resizer target:', target);
            this.isResizing = false;
            return;
        }

        resizer.classList.add('resizing');
        if (container) {
            container.classList.add('resizing');
        }
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';

        e.preventDefault();
        e.stopPropagation();
    }

    resize(e) {
        if (!this.isResizing || !this.currentResizer) return;

        const container = document.querySelector('.app-container');
        if (!container) return;

        const containerWidth = container.offsetWidth;
        const maxWidth = containerWidth * this.maxWidthPercent;

        let newWidth;
        const target = this.currentResizer.dataset.target;

        if (target === 'sidebar') {
            // Sidebar resizes from left to right (при перетаскивании вправо увеличивается)
            const delta = e.clientX - this.startX;
            newWidth = this.startWidth + delta;
        } else if (target === 'main') {
            // Detail panel resizes from right to left (при перетаскивании влево увеличивается)
            const delta = this.startX - e.clientX;
            newWidth = this.startWidth + delta;
        } else {
            return;
        }

        // Constrain width
        newWidth = Math.max(this.minWidth, Math.min(newWidth, maxWidth));

        // Update CSS variable - grid-template-columns использует переменные, поэтому обновление автоматическое
        container.style.setProperty(this.cssVariable, `${newWidth}px`);
        
        // Для отладки: проверяем, что переменная установлена
        const actualValue = container.style.getPropertyValue(this.cssVariable);
        if (!actualValue) {
            console.warn(`Failed to set CSS variable ${this.cssVariable} to ${newWidth}px`);
        }
    }

    stopResize() {
        if (!this.isResizing) return;

        this.isResizing = false;

        if (this.currentResizer) {
            this.currentResizer.classList.remove('resizing');
            this.currentResizer = null;
        }

        const container = document.querySelector('.app-container');
        if (container) {
            container.classList.remove('resizing');
        }

        document.body.style.cursor = '';
        document.body.style.userSelect = '';
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new PanelResizer();
});
