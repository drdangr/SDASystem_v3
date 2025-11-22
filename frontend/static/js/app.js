// SDASystem Frontend Application - Refactored with Modular Views
const API_BASE = '/api';

class SDAApp {
    constructor() {
        // Application state
        this.stories = [];
        this.currentStory = null;
        this.currentNews = null;
        this.currentActor = null;
        this.viewMode = 'list'; // 'list' or 'graph'

        // Initialize EventBus for inter-module communication
        this.eventBus = new EventBus();

        // Initialize view modules
        this.listView = new ListView('storiesList', this.eventBus);
        this.graphView = new GraphView('storiesList', this.eventBus, API_BASE);
        this.storyView = new StoryView('.main-panel-content', this.eventBus, API_BASE);
        this.detailsView = new DetailsView('.detail-panel-content', this.eventBus, API_BASE);
        this.timelineView = new TimelineView('timelineEvents', this.eventBus, API_BASE);

        this.init();
    }

    init() {
        this.setupEventListeners();
        this.setupEventBusListeners();
        this.restorePanelStates();
        this.loadData();
    }

    async loadData() {
        try {
            const response = await fetch(`${API_BASE}/stories`);
            this.stories = await response.json();

            // Render stories in current view mode
            if (this.viewMode === 'list') {
                this.listView.render(this.stories);
            } else {
                this.graphView.render(this.stories);
            }

            // Select first story if available
            if (this.stories.length > 0 && !this.currentStory) {
                this.selectStory(this.stories[0].id);
            }

            this.updateStats();
        } catch (error) {
            console.error('Failed to load data:', error);
        }
    }

    setupEventListeners() {
        // View mode toggle
        document.getElementById('viewList')?.addEventListener('click', () => {
            this.viewMode = 'list';
            this.updateViewMode();
        });

        document.getElementById('viewGraph')?.addEventListener('click', () => {
            this.viewMode = 'graph';
            this.updateViewMode();
        });

        // Timeline zoom controls
        document.getElementById('zoomDay')?.addEventListener('click', () => {
            this.timelineView.setZoom('day');
        });

        document.getElementById('zoomWeek')?.addEventListener('click', () => {
            this.timelineView.setZoom('week');
        });

        document.getElementById('zoomMonth')?.addEventListener('click', () => {
            this.timelineView.setZoom('month');
        });

        // Panel minimization - use event delegation
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('minimize-btn')) {
                e.stopPropagation();
                const panel = e.target.dataset.panel;
                if (panel) {
                    this.togglePanel(panel);
                }
            }
        });
    }

    setupEventBusListeners() {
        // Story selection
        this.eventBus.on('story:selected', async (storyId) => {
            await this.selectStory(storyId);
        });

        // News selection
        this.eventBus.on('news:selected', async (newsId) => {
            await this.selectNews(newsId);
        });

        // Actor selection
        this.eventBus.on('actor:selected', async (actorId) => {
            await this.selectActor(actorId);
        });
    }

    async selectStory(storyId) {
        const story = this.stories.find(s => s.id === storyId);
        if (!story) return;

        this.currentStory = story;

        // Update list selection
        if (this.viewMode === 'list') {
            this.listView.currentStoryId = storyId;
            this.listView.updateSelection();
        }

        // Render story details
        await this.storyView.render(story);

        // Load timeline
        await this.timelineView.loadStoryTimeline(storyId);

        // Clear detail panel
        this.detailsView.clear();
    }

    async selectNews(newsId) {
        try {
            const response = await fetch(`${API_BASE}/news/${newsId}`);
            this.currentNews = await response.json();
            await this.detailsView.renderNews(this.currentNews);
        } catch (error) {
            console.error('Failed to load news:', error);
        }
    }

    async selectActor(actorId) {
        try {
            const response = await fetch(`${API_BASE}/actors/${actorId}`);
            this.currentActor = await response.json();
            await this.detailsView.renderActor(this.currentActor);
        } catch (error) {
            console.error('Failed to load actor:', error);
        }
    }

    updateViewMode() {
        // Update button states
        document.getElementById('viewList')?.classList.toggle('active', this.viewMode === 'list');
        document.getElementById('viewGraph')?.classList.toggle('active', this.viewMode === 'graph');

        // Render in appropriate view
        if (this.viewMode === 'list') {
            this.listView.render(this.stories);
            if (this.currentStory) {
                this.listView.currentStoryId = this.currentStory.id;
                this.listView.updateSelection();
            }
        } else {
            this.graphView.render(this.stories);
        }
    }

    updateStats() {
        const statsStories = document.getElementById('statsStories');
        const statsNews = document.getElementById('statsNews');
        const statsActors = document.getElementById('statsActors');

        if (statsStories) statsStories.textContent = this.stories.length;

        // Calculate total news and actors
        const totalNews = this.stories.reduce((sum, s) => sum + s.size, 0);
        const uniqueActors = new Set(this.stories.flatMap(s => s.top_actors));

        if (statsNews) statsNews.textContent = totalNews;
        if (statsActors) statsActors.textContent = uniqueActors.size;
    }

    // Panel minimization methods
    togglePanel(panelName) {
        const container = document.querySelector('.app-container');
        const className = `${panelName}-minimized`;
        const isMinimized = container.classList.contains(className);

        container.classList.toggle(className);

        // Update button text
        const button = document.querySelector(`[data-panel="${panelName}"]`);
        if (button) {
            button.textContent = isMinimized ? '−' : '_';
        }

        // Save state to localStorage
        const minimizedPanels = this.getMinimizedPanels();
        localStorage.setItem('minimizedPanels', JSON.stringify(minimizedPanels));
    }

    getMinimizedPanels() {
        const container = document.querySelector('.app-container');
        const panels = ['sidebar', 'main', 'detail', 'timeline'];
        return panels.filter(panel => container.classList.contains(`${panel}-minimized`));
    }

    restorePanelStates() {
        const minimizedPanels = JSON.parse(localStorage.getItem('minimizedPanels') || '[]');
        const container = document.querySelector('.app-container');

        minimizedPanels.forEach(panel => {
            container.classList.add(`${panel}-minimized`);
            const button = document.querySelector(`[data-panel="${panel}"]`);
            if (button) button.textContent = '_';
        });
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.sdaApp = new SDAApp();
});
