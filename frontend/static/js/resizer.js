/**
 * Panel Resizer - Управление размерами панелей с Flexbox
 * 
 * Логика:
 * - Левый ресайзер (resizer-left): изменяет flex-basis sidebar
 * - Правый ресайзер (resizer-right): изменяет flex-basis detail
 * - Горизонтальный ресайзер: изменяет height timeline
 */
class PanelResizer {
    constructor() {
        this.isResizing = false;
        this.currentResizer = null;
        this.startPos = 0;
        this.startSize = 0;
        
        // Ограничения
        this.minWidth = 150;
        this.maxWidthPercent = 0.5; // Максимум 50% ширины контейнера
        this.minHeight = 100;
        this.maxHeightPercent = 0.6;
        
        this.init();
    }

    init() {
        // Вертикальные ресайзеры
        document.querySelectorAll('.resizer-vertical').forEach(resizer => {
            resizer.addEventListener('mousedown', (e) => this.startResize(e, resizer, 'horizontal'));
        });
        
        // Горизонтальный ресайзер (если есть)
        document.querySelectorAll('.resizer-horizontal').forEach(resizer => {
            resizer.addEventListener('mousedown', (e) => this.startResize(e, resizer, 'vertical'));
        });
        
        // Глобальные обработчики
        document.addEventListener('mousemove', (e) => this.resize(e));
        document.addEventListener('mouseup', () => this.stopResize());
        
        console.log('PanelResizer initialized');
    }

    startResize(e, resizer, direction) {
        e.preventDefault();
        
        this.isResizing = true;
        this.currentResizer = resizer;
        this.direction = direction;
        
        if (direction === 'horizontal') {
            this.startPos = e.clientX;
            
            // Определяем, какую панель изменяем
            if (resizer.classList.contains('resizer-left')) {
                // Левый ресайзер - изменяем sidebar
                this.targetPanel = document.querySelector('.sidebar');
                this.resizeDirection = 1; // При движении вправо - увеличиваем
            } else if (resizer.classList.contains('resizer-right')) {
                // Правый ресайзер - изменяем detail
                this.targetPanel = document.querySelector('.detail-panel');
                this.resizeDirection = -1; // При движении вправо - уменьшаем
            }
            
            if (this.targetPanel) {
                this.startSize = this.targetPanel.offsetWidth;
            }
        } else {
            // Вертикальный ресайз (timeline)
            this.startPos = e.clientY;
            this.targetPanel = document.querySelector('.timeline-panel');
            this.resizeDirection = -1; // При движении вверх - увеличиваем
            
            if (this.targetPanel) {
                this.startSize = this.targetPanel.offsetHeight;
            }
        }
        
        // Проверяем, что панель не минимизирована
        if (this.targetPanel && this.targetPanel.classList.contains('minimized')) {
            this.isResizing = false;
            return;
        }
        
        // Добавляем классы для визуальной обратной связи
        resizer.classList.add('resizing');
        document.body.style.cursor = direction === 'horizontal' ? 'col-resize' : 'row-resize';
        document.body.style.userSelect = 'none';
    }

    resize(e) {
        if (!this.isResizing || !this.currentResizer || !this.targetPanel) return;
        
        let newSize;
        
        if (this.direction === 'horizontal') {
            const delta = (e.clientX - this.startPos) * this.resizeDirection;
            newSize = this.startSize + delta;
            
            // Ограничения
            const container = document.querySelector('.panels-container');
            const maxWidth = container ? container.offsetWidth * this.maxWidthPercent : 600;
            newSize = Math.max(this.minWidth, Math.min(newSize, maxWidth));
            
            // Устанавливаем flex-basis
            this.targetPanel.style.flexBasis = `${newSize}px`;
        } else {
            const delta = (e.clientY - this.startPos) * this.resizeDirection;
            newSize = this.startSize + delta;
            
            // Ограничения для timeline
            const maxHeight = (window.innerHeight - 60) * this.maxHeightPercent;
            newSize = Math.max(this.minHeight, Math.min(newSize, maxHeight));
            
            // Устанавливаем height
            this.targetPanel.style.height = `${newSize}px`;
        }
    }

    stopResize() {
        if (!this.isResizing) return;
        
        this.isResizing = false;
        
        if (this.currentResizer) {
            this.currentResizer.classList.remove('resizing');
        }
        
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        
        this.currentResizer = null;
        this.targetPanel = null;
    }
}

// Инициализация при загрузке DOM
document.addEventListener('DOMContentLoaded', () => {
    window.panelResizer = new PanelResizer();
});
