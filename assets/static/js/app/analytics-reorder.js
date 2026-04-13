// Analytics dashboard widget reordering
let analyticsWidgetOrder = [];
const ANALYTICS_ORDER_KEY = 'shakshuka_analytics_widget_order_v1';

function loadAnalyticsWidgetOrder() {
    try {
        if (!window.localStorage) return;
        const raw = window.localStorage.getItem(ANALYTICS_ORDER_KEY);
        if (!raw) return;
        const arr = JSON.parse(raw);
        if (Array.isArray(arr)) {
            analyticsWidgetOrder = arr.filter(id => typeof id === 'string' && id.trim().length > 0);
        }
    } catch (e) {
        // best-effort only
    }
}

function saveAnalyticsWidgetOrder() {
    try {
        if (!window.localStorage) return;
        window.localStorage.setItem(ANALYTICS_ORDER_KEY, JSON.stringify(analyticsWidgetOrder));
    } catch (e) {
        // best-effort only
    }
}

function initializeAnalyticsReorder() {
    const grid = document.querySelector('.dashboard-grid');
    if (!grid) return;

    const cards = Array.from(grid.querySelectorAll('.stats-card, .strike-calendar-card'));
    if (cards.length === 0) return;

    // Assign IDs to cards that don't have them
    cards.forEach((card, index) => {
        if (!card.id) {
            const title = card.querySelector('p, .strike-calendar-title');
            const titleText = (title && title.textContent) || `widget-${index}`;
            const cardId = `analytics-card-${titleText.toLowerCase().replace(/\s+/g, '-')}`;
            card.id = cardId;
        }
    });

    // Get all current card IDs
    const allCardIds = cards.map(c => c.id);

    // If no saved order yet, save the current order
    if (analyticsWidgetOrder.length === 0) {
        analyticsWidgetOrder = allCardIds;
        saveAnalyticsWidgetOrder();
    } else {
        // Reorder the grid based on saved order, then append any new cards
        const orderedIds = analyticsWidgetOrder.filter(id => allCardIds.includes(id));
        const newIds = allCardIds.filter(id => !analyticsWidgetOrder.includes(id));
        analyticsWidgetOrder = orderedIds.concat(newIds);

        // Reorder DOM elements
        const cardMap = new Map(cards.map(c => [c.id, c]));
        analyticsWidgetOrder.forEach(id => {
            const card = cardMap.get(id);
            if (card) {
                grid.appendChild(card); // Reappend to change order
            }
        });
        saveAnalyticsWidgetOrder();
    }

    // Make cards draggable
    cards.forEach(card => {
        card.draggable = true;
        card.style.cursor = 'grab';

        card.addEventListener('dragstart', (e) => {
            card.style.opacity = '0.5';
            card.style.cursor = 'grabbing';
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', card.id);
        });

        card.addEventListener('dragend', (e) => {
            card.style.opacity = '';
            card.style.cursor = 'grab';
        });

        card.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            card.style.borderTop = '3px solid var(--accent-color)';
        });

        card.addEventListener('dragleave', (e) => {
            card.style.borderTop = '';
        });

        card.addEventListener('drop', (e) => {
            e.preventDefault();
            card.style.borderTop = '';
            const draggedId = e.dataTransfer.getData('text/plain');
            if (draggedId && draggedId !== card.id) {
                // Reorder in the saved order array
                const draggedIdx = analyticsWidgetOrder.indexOf(draggedId);
                const targetIdx = analyticsWidgetOrder.indexOf(card.id);
                if (draggedIdx !== -1 && targetIdx !== -1) {
                    analyticsWidgetOrder.splice(draggedIdx, 1);
                    analyticsWidgetOrder.splice(targetIdx, 0, draggedId);
                    saveAnalyticsWidgetOrder();

                    // Reorder DOM
                    const draggedCard = document.getElementById(draggedId);
                    if (draggedCard) {
                        const allCards = Array.from(grid.querySelectorAll('.stats-card, .strike-calendar-card'));
                        if (allCards.indexOf(draggedCard) < allCards.indexOf(card)) {
                            card.parentNode.insertBefore(draggedCard, card);
                        } else {
                            card.parentNode.insertBefore(draggedCard, card.nextSibling);
                        }
                    }
                }
            }
        });
    });
}

// Initialize when analytics page is shown
if (typeof window !== 'undefined') {
    const origShowPage = window.showPage;
    if (typeof origShowPage === 'function') {
        window.showPage = function(pageName) {
            const result = origShowPage.call(this, pageName);
            if (pageName === 'analytics') {
                loadAnalyticsWidgetOrder();
                setTimeout(initializeAnalyticsReorder, 150);
            }
            return result;
        };
    }
}
