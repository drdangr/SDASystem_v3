export class MainPanel {
    constructor(storyView) {
        this.storyView = storyView;
    }

    async render(story) {
        await this.storyView.render(story);
    }

    clear() {
        this.storyView.clear();
    }
}

