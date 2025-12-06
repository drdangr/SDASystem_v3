export class DetailPanel {
    constructor(detailsView) {
        this.detailsView = detailsView;
    }

    async renderNews(news) {
        await this.detailsView.renderNews(news);
    }

    async renderActor(actor) {
        await this.detailsView.renderActor(actor);
    }

    clear() {
        this.detailsView.clear?.();
    }
}

