// Navbar compact schedule card
(function(){
    function apiCallCompat(url, options = {}) {
        if (typeof window.apiCall === 'function') {
            return window.apiCall(url, options);
        }
        const headers = {
            ...(options.headers || {})
        };
        if (!(options.body instanceof FormData)) {
            headers['Content-Type'] = 'application/json';
        }
        return fetch(url, {
            ...options,
            credentials: 'include',
            headers
        });
    }

    function getDateKey(date){
        const y = date.getFullYear();
        const m = String(date.getMonth()+1).padStart(2,'0');
        const d = String(date.getDate()).padStart(2,'0');
        return `${y}-${m}-${d}`;
    }
    function toMinutes(h, m){ return (h*60)+m; }
    function formatTime(h, m){
        const hour = (h % 12) || 12;
        const min = String(m).padStart(2,'0');
        const ampm = h < 12 ? 'AM' : 'PM';
        return `${hour}:${min} ${ampm}`;
    }
    async function fetchScheduleFor(date){
        try {
            const resp = await apiCallCompat('/api/planner-v2/schedule');
            const data = await resp.json();
            const key = getDateKey(date);
            const byHour = (data && data.scheduled_tasks && data.scheduled_tasks[key]) || {};
            const entries = [];
            Object.entries(byHour).forEach(([hourKey, arr])=>{
                const baseHour = parseInt(hourKey,10) || 0;
                (arr || []).forEach(t=>{
                    const h = (typeof t.scheduled_hour === 'number') ? t.scheduled_hour : baseHour;
                    const mm = (typeof t.scheduled_minute === 'number') ? t.scheduled_minute : (t.scheduled_minute ? parseInt(t.scheduled_minute,10) : 0);
                    const dur = parseInt(t.scheduled_duration || t.estimated_duration || 30,10);
                    entries.push({ id: t.id, title: t.title, startH: h, startM: mm, dur });
                });
            });
            // Dedup by id (prefer earliest start)
            const byId = new Map();
            for(const e of entries){
                if(!byId.has(e.id)) byId.set(e.id, e);
                else {
                    const ex = byId.get(e.id);
                    const exMin = toMinutes(ex.startH, ex.startM);
                    const curMin = toMinutes(e.startH, e.startM);
                    if (curMin < exMin) byId.set(e.id, e);
                }
            }
            return Array.from(byId.values()).sort((a,b)=> toMinutes(a.startH,a.startM) - toMinutes(b.startH,b.startM));
        } catch (e) {
            return [];
        }
    }
    async function updateCard(){
        const card = document.getElementById('nav-compact-schedule');
        if (!card) return;

        const navigateToPlanner = () => {
            try { navigateToPage('planner'); } catch(e) {
                const btn = document.querySelector('.nav-item[data-page="planner"]');
                if (btn) btn.click();
            }
            try { if (typeof window.ensurePlannerV2Init === 'function') { window.ensurePlannerV2Init(); } } catch(e) {}
        };

        const makePlanLink = (el) => {
            if (!el) return;
            el.innerHTML = '<a href="#" class="nav-plan-now-link">Plan now?</a>';
            const link = el.querySelector('.nav-plan-now-link');
            if (link) {
                link.addEventListener('click', (e) => {
                    e.preventDefault();
                    navigateToPlanner();
                }, { once: true });
            }
        };

        const now = new Date();
        const nowMin = toMinutes(now.getHours(), now.getMinutes());
        const list = await fetchScheduleFor(now);

        // If nothing scheduled today, show CTA to plan
        if (Array.isArray(list) && list.length === 0) {
            const curTitleEl = card.querySelector('#nav-current-title');
            const curTimeEl = card.querySelector('#nav-current-time');
            const nextTitleEl = card.querySelector('#nav-next-title');
            const nextTimeEl = card.querySelector('#nav-next-time');
            const curBadge = card.querySelector('#nav-current-badge');
            const nextBadge = card.querySelector('#nav-next-badge');
            if (curTitleEl) curTitleEl.textContent = 'Nothing scheduled';
            makePlanLink(curTimeEl);
            if (nextTitleEl) nextTitleEl.textContent = 'None';
            makePlanLink(nextTimeEl);
            if (curBadge) curBadge.textContent = 'Now';
            if (nextBadge) nextBadge.textContent = 'Next';
            return;
        }

        let current = null, next = null;
        for(const t of list){
            const start = toMinutes(t.startH, t.startM);
            const end = start + t.dur;
            if (nowMin >= start && nowMin < end) { current = t; break; }
            if (nowMin < start) { next = t; break; }
        }
        if (!current){
            // ensure next if none yet
            for(const t of list){
                const start = toMinutes(t.startH, t.startM);
                if (nowMin < start) { next = t; break; }
            }
        } else {
            // next after current
            const after = list.filter(t=> toMinutes(t.startH,t.startM) >= (toMinutes(current.startH,current.startM)+current.dur));
            if (after.length) next = after[0];
        }
        const curTitleEl = card.querySelector('#nav-current-title');
        const curTimeEl = card.querySelector('#nav-current-time');
        const nextTitleEl = card.querySelector('#nav-next-title');
        const nextTimeEl = card.querySelector('#nav-next-time');
        const curBadge = card.querySelector('#nav-current-badge');
        const nextBadge = card.querySelector('#nav-next-badge');

        // Realtime CTA: if neither current nor next, offer to plan
        if (!current && !next) {
            if (curTitleEl) curTitleEl.textContent = 'Nothing scheduled';
            makePlanLink(curTimeEl);
            if (nextTitleEl) nextTitleEl.textContent = 'None';
            makePlanLink(nextTimeEl);
            if (curBadge) curBadge.textContent = 'Now';
            if (nextBadge) nextBadge.textContent = 'Next';
            return;
        }

        if (current){
            curTitleEl.textContent = current.title || 'Untitled';
            const endTotal = current.startH*60+current.startM+current.dur;
            curTimeEl.textContent = `${formatTime(current.startH,current.startM)} - ${formatTime(Math.floor(endTotal/60), endTotal%60)}`;
        } else {
            curTitleEl.textContent = 'None';
            curTimeEl.textContent = '—';
        }
        if (next){
            nextTitleEl.textContent = next.title || 'Untitled';
            nextTimeEl.textContent = `${formatTime(next.startH,next.startM)}`;
        } else {
            nextTitleEl.textContent = 'None';
            nextTimeEl.textContent = '—';
        }
        if (curBadge) curBadge.textContent = 'Now';
        if (nextBadge) nextBadge.textContent = 'Next';

        // Slot-level CTA cases
        if (current && !next) {
            // Offer to plan in the Next slot
            if (nextTitleEl) nextTitleEl.textContent = 'None';
            makePlanLink(nextTimeEl);
        }
        if (!current && next) {
            // Offer to plan in the Now slot
            if (curTitleEl) curTitleEl.textContent = 'None';
            makePlanLink(curTimeEl);
        }
    }
window.NavbarScheduleCard = {
        init(){
            if (this._timer) clearInterval(this._timer);
            this.applyStyle(this.getStyle());
            updateCard();
            this._timer = setInterval(updateCard, 60000);
        },
        update: updateCard,
        getStyle(){
            try { return localStorage.getItem('navbar_planner_style') || 'modern'; } catch(e){ return 'modern'; }
        },
        applyStyle(style){
            const card = document.getElementById('nav-compact-schedule');
            if (!card) return;
            card.classList.remove('clean','modern');
            card.classList.add(style === 'modern' ? 'modern' : 'clean');
        },
        setStyle(style){
            try { localStorage.setItem('navbar_planner_style', style); } catch(e) {}
            this.applyStyle(style);
            updateCard();
        }
    };
})();
