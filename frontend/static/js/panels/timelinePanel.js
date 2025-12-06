export class TimelinePanel {
    constructor(timelineView) {
        this.timelineView = timelineView;
    }

    async render(storyId) {
        await this.timelineView.loadStoryTimeline(storyId);
    }

    clear() {
        this.timelineView.clear();
    }
}

