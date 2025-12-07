export class InitModal {
    constructor() {
        this.modal = document.getElementById('initModal');
        this.progressBar = this.modal?.querySelector('.progress-bar');
        this.progressText = this.modal?.querySelector('.progress-text');
        this.log = this.modal?.querySelector('.init-log');
        this.current = this.modal?.querySelector('.progress-current');
        this.counts = this.modal?.querySelector('.progress-counts');
    }

    show() {
        if (this.modal) this.modal.style.display = 'block';
    }

    hide() {
        if (this.modal) this.modal.style.display = 'none';
    }

    setProgress(processed, total, message = '') {
        if (!this.progressBar || !this.progressText) return;
        const percent = total > 0 ? Math.floor((processed / total) * 100) : 0;
        this.progressBar.style.width = `${percent}%`;
        this.progressText.textContent = `${percent}% ${message || ''}`;

        if (this.counts) {
            this.counts.textContent = `Processed: ${processed}/${total}`;
        }
    }

    appendLog(line) {
        if (!this.log) return;
        const div = document.createElement('div');
        div.textContent = line;
        this.log.appendChild(div);
        this.log.scrollTop = this.log.scrollHeight;
    }

    applyStatus(status) {
        const progress = status?.progress || {};
        this.setProgress(progress.processed || 0, progress.total || 0, progress.message || '');

        if (this.current) {
            const title = progress.current_news_title || '';
            this.current.textContent = title ? `Now: ${title}` : '';
        }

        if (this.counts && status?.actors_count !== undefined) {
            this.counts.textContent = `Processed: ${progress.processed || 0}/${progress.total || 0} • Actors: ${status.actors_count}`;
        }

        if (status?.initialized) {
            this.hide();
        } else {
            this.show();
        }
    }
}

