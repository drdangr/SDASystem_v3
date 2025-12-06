export function qs(selector, root = document) {
    return root.querySelector(selector);
}

export function qsa(selector, root = document) {
    return Array.from(root.querySelectorAll(selector));
}

export function on(el, event, handler) {
    if (el) el.addEventListener(event, handler);
}

export function toggleClass(el, cls, state) {
    if (!el) return;
    if (state === undefined) {
        el.classList.toggle(cls);
    } else {
        el.classList.toggle(cls, state);
    }
}

