// SDASystem Frontend Application - Refactored with Modular Views
import { SidebarPanel } from './panels/sidebar.js';
import { MainPanel } from './panels/mainPanel.js';
import { DetailPanel } from './panels/detailPanel.js';
import { TimelinePanel } from './panels/timelinePanel.js';
import { ListView } from './views/ListView.js';
import { GraphView } from './views/GraphView.js';
import { StoryView } from './views/StoryView.js';
import { DetailsView } from './views/DetailsView.js';
import { TimelineView } from './views/TimelineView.js';
import { LLMSettingsModal } from './ui/llmSettings.js';
import { llmGenerate } from './api/llmClient.js';

const API_BASE = '/api';

class SDAApp {
    constructor() {
        // Application state
        this.stories = [];
        this.currentStory = null;
        this.currentNews = null;
        this.currentActor = null;
        this.viewMode = 'list'; // kept for backward compat

        // Initialize EventBus for inter-module communication
        this.eventBus = new EventBus();

        // Initialize view modules
        this.listView = new ListView('storiesList', this.eventBus);
        this.graphView = new GraphView('storiesList', this.eventBus, API_BASE);
        this.storyView = new StoryView('.main-panel-content', this.eventBus, API_BASE);
        this.detailsView = new DetailsView('.detail-panel-content', this.eventBus, API_BASE);
        this.timelineView = new TimelineView('.timeline-content', this.eventBus, API_BASE);

        // Panels abstraction
        this.sidebarPanel = new SidebarPanel(this.eventBus, this.listView, this.graphView, (mode) => {
            this.viewMode = mode;
        });
        this.mainPanel = new MainPanel(this.storyView);
        this.detailPanel = new DetailPanel(this.detailsView);
        this.timelinePanel = new TimelinePanel(this.timelineView);

        // LLM settings modal
        this.llmSettings = null;
        this.llmModal = new LLMSettingsModal('llmSettings', (state) => {
            this.llmSettings = state;
        });
        this.llmDebugModal = this.initLLMDebugModal();

        this.init();
    }

    init() {
        this.setupEventListeners();
        this.setupEventBusListeners();
        this.restorePanelStates();
        this.sidebarPanel.init();
        this.llmModal.init();
        this.llmSettings = this.llmModal.state;
        this.loadData();
    }

    initLLMDebugModal() {
        const modal = document.querySelector('#llmDebugModal');
        const openBtn = document.querySelector('#llmDebugBtn');
        const closeBtn = document.querySelector('#llmDebugClose');
        const saveBtn = document.querySelector('#llmDebugSave');
        const textarea = document.querySelector('#llmDebugContent');

        const show = () => {
            textarea.value = window.lastLLMDebug || 'Нет данных';
            modal?.classList.add('open');
        };
        const hide = () => modal?.classList.remove('open');

        openBtn?.addEventListener('click', show);
        closeBtn?.addEventListener('click', hide);
        saveBtn?.addEventListener('click', hide);

        return { show, hide, textarea };
    }

    // LLM helper (used in next steps for summary/bullets)
    async callLLM(task, title, text) {
        return llmGenerate({
            task,
            title,
            text,
            settings: this.llmSettings || {}
        });
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

        // Actors updated via LLM for a news item
        this.eventBus.on('actors:updated', async () => {
            await this.refreshStories();
        });
    }

    async selectStory(storyId) {
        const story = this.stories.find(s => s.id === storyId);
        if (!story) return;

        this.currentStory = story;

        // Update list selection
            this.listView.currentStoryId = storyId;
            this.listView.updateSelection();

        // Render story details
        await this.mainPanel.render(story);

        // Load timeline
        await this.timelinePanel.render(storyId);

        // Clear detail panel
        this.detailPanel.clear();
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
        this.sidebarPanel.viewMode = this.viewMode;
        this.sidebarPanel.updateViewMode();
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

    async refreshStories() {
        try {
            const prevStoryId = this.currentStory?.id;
            const prevNewsId = this.currentNews?.id;
            const response = await fetch(`${API_BASE}/stories`);
            this.stories = await response.json();

            if (this.viewMode === 'list') {
                this.listView.render(this.stories);
            } else {
                this.graphView.render(this.stories);
            }

            if (prevStoryId) {
                await this.selectStory(prevStoryId);
                if (prevNewsId) {
                    await this.selectNews(prevNewsId);
                }
            }

            this.updateStats();
        } catch (error) {
            console.error('Failed to refresh stories:', error);
        }
    }

    // Panel minimization methods
    // Маппинг имён панелей к селекторам
    getPanelElement(panelName) {
        const selectors = {
            'sidebar': '.sidebar',
            'main': '.main-panel',
            'detail': '.detail-panel',
            'timeline': '.timeline-panel'
        };
        return document.querySelector(selectors[panelName]);
    }

    togglePanel(panelName) {
        const panel = this.getPanelElement(panelName);
        if (!panel) return;
        
        // Toggle the minimized class on the panel itself
        panel.classList.toggle('minimized');
        
        // Check state AFTER toggle
        const isNowMinimized = panel.classList.contains('minimized');

        // Update button text based on NEW state
        const button = document.querySelector(`[data-panel="${panelName}"]`);
        if (button) {
            button.textContent = isNowMinimized ? '+' : '−';
        }

        // Обновляем flex для оставшихся панелей
        this.updatePanelsFlex();

        // Save state to localStorage
        const minimizedPanels = this.getMinimizedPanels();
        localStorage.setItem('minimizedPanels', JSON.stringify(minimizedPanels));
    }

    // Обновляет flex панелей в зависимости от того, какие свёрнуты
    updatePanelsFlex() {
        const sidebar = document.querySelector('.sidebar');
        const main = document.querySelector('.main-panel');
        const detail = document.querySelector('.detail-panel');

        const sidebarMin = sidebar?.classList.contains('minimized');
        const mainMin = main?.classList.contains('minimized');
        const detailMin = detail?.classList.contains('minimized');

        // Сбрасываем flex для не-минимизированных панелей
        if (sidebar && !sidebarMin) {
            // Если main свёрнут, sidebar должен расти
            sidebar.style.flex = mainMin ? '1 1 auto' : '0 0 300px';
        }

        if (main && !mainMin) {
            // Main всегда растёт, если не свёрнут
            main.style.flex = '1 1 auto';
        }

        if (detail && !detailMin) {
            // Если main свёрнут, detail тоже должен расти
            detail.style.flex = mainMin ? '1 1 auto' : '0 0 350px';
        }
    }

    getMinimizedPanels() {
        const panels = ['sidebar', 'main', 'detail', 'timeline'];
        return panels.filter(panelName => {
            const panel = this.getPanelElement(panelName);
            return panel && panel.classList.contains('minimized');
        });
    }

    restorePanelStates() {
        const minimizedPanels = JSON.parse(localStorage.getItem('minimizedPanels') || '[]');

        minimizedPanels.forEach(panelName => {
            const panel = this.getPanelElement(panelName);
            if (panel) {
                panel.classList.add('minimized');
            }
            const button = document.querySelector(`[data-panel="${panelName}"]`);
            if (button) button.textContent = '+';
        });

        // Обновляем flex после восстановления состояний
        this.updatePanelsFlex();
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.sdaApp = new SDAApp();
});
