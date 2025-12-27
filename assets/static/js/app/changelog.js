// Changelog functions
async function loadChangelog() {
    try {
        const response = await fetch('/api/changelog');
        if (response.ok) {
            const changelogText = await response.text();
            return changelogText;
        } else {
            throw new Error('Failed to load changelog');
        }
    } catch (error) {
        Utils.Logger.error('Failed to load changelog:', error);
        return 'Error loading changelog. Please check your connection and try again.';
    }
}

function parseChangelogToSections(markdown) {
    // Parse the changelog markdown into version sections (including consolidated ranges),
    // then group by major version.
    const sections = [];
    const lines = markdown.split('\n');
    let currentSection = null;

    function normalizeLine(raw) {
        // The changelog file may contain encoding artifacts (e.g. BOM, zero-width
        // spaces) that can break simple startsWith checks. Normalize aggressively
        // for header detection.
        return (raw || '')
            .replace(/^\uFEFF/, '')
            .replace(/[\u200B-\u200D\uFEFF]/g, '')
            .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F-\u009F]/g, '')
            .replace(/\u00A0/g, ' ')
            .trim();
    }

    for (let i = 0; i < lines.length; i++) {
        const line = normalizeLine(lines[i]);

        const versionHeader = line.match(/^##\s*Version\s+(.+)$/i);
        const versionsHeader = line.match(/^##\s*Versions\s+(.+)$/i);

        // Check for single-version headers (## Version X.X)
        if (versionHeader) {
            if (currentSection) {
                sections.push(currentSection);
            }
            const headerRest = versionHeader[1];
            const numericVersionMatch = headerRest.match(/(\d+(?:\.\d+)+)/);
            const numericVersion = numericVersionMatch
                ? numericVersionMatch[1]
                : headerRest.split(' - ')[0].trim();
            currentSection = {
                version: numericVersion,
                title: line.replace(/^##\s*/i, ''),
                content: [],
                date: null,
                versionRange: null
            };
        }
        // Check for consolidated range headers (## Versions 11.0 – 12.1 – ...)
        else if (versionsHeader) {
            if (currentSection) {
                sections.push(currentSection);
            }
            const headerRest = versionsHeader[1];
            const versionMatches = headerRest.match(/(\d+(?:\.\d+)+)/g) || [];
            // Use the last numeric token as the synthetic version for sorting (e.g. 12.1)
            const syntheticVersion = versionMatches.length
                ? versionMatches[versionMatches.length - 1]
                : headerRest.split(' - ')[0].trim();

            let versionRange = null;
            if (versionMatches.length >= 2) {
                const startMajor = parseInt(versionMatches[0].split('.')[0], 10);
                const endMajor = parseInt(versionMatches[versionMatches.length - 1].split('.')[0], 10);
                if (Number.isFinite(startMajor) && Number.isFinite(endMajor)) {
                    versionRange = { startMajor, endMajor };
                }
            }

            currentSection = {
                version: syntheticVersion,
                title: line.replace(/^##\s*/i, ''),
                content: [],
                date: null,
                versionRange
            };
        }
        // Check for release date / period
        else if ((line.startsWith('Release Date:') || line.startsWith('Release Period:')) && currentSection) {
            currentSection.date = line.replace(/^Release (Date|Period):/i, '').trim();
        }
        // Add content to current section (skip blank lines outside sections)
        else if (currentSection && line) {
            currentSection.content.push(line);
        }
    }

    // Add the last section
    if (currentSection) {
        sections.push(currentSection);
    }

    // Helper to compare two version strings (semver-ish)
    function compareVersions(a, b) {
        const va = (a || '').split('.').map(Number);
        const vb = (b || '').split('.').map(Number);
        const maxLen = Math.max(va.length, vb.length);
        for (let i = 0; i < maxLen; i++) {
            const na = va[i] || 0;
            const nb = vb[i] || 0;
            if (na !== nb) return na - nb;
        }
        return 0;
    }

    // Sort by version (latest first) - simple version comparison
    sections.sort((a, b) => compareVersions(b.version, a.version));

    // Group sections by major version (e.g. 13.7, 13.6 → major "13").
    // Consolidated range sections (with versionRange) are attached to every
    // major they cover (e.g. 11 and 12 for "Versions 11.0 – 12.1").
    const groupsMap = new Map();

    sections.forEach(section => {
        if (section.versionRange) {
            const { startMajor, endMajor } = section.versionRange;
            if (Number.isFinite(startMajor) && Number.isFinite(endMajor)) {
                for (let majorNum = startMajor; majorNum <= endMajor; majorNum++) {
                    const majorKey = String(majorNum);
                    if (!groupsMap.has(majorKey)) {
                        groupsMap.set(majorKey, {
                            majorVersion: majorKey,
                            sections: []
                        });
                    }
                    groupsMap.get(majorKey).sections.push(section);
                }
                return;
            }
        }

        const rawVersion = section.version || '';
        const major = (rawVersion.split('.')[0] || rawVersion || '0').trim();
        if (!groupsMap.has(major)) {
            groupsMap.set(major, {
                majorVersion: major,
                sections: []
            });
        }
        groupsMap.get(major).sections.push(section);
    });

    // Sort sections within each major group (latest minor first)
    groupsMap.forEach(group => {
        group.sections.sort((a, b) => compareVersions(b.version, a.version));
    });

    // Convert to an array of groups sorted by major version (latest first)
    const groups = Array.from(groupsMap.values()).sort((a, b) => {
        const ma = parseInt(a.majorVersion, 10) || 0;
        const mb = parseInt(b.majorVersion, 10) || 0;
        return mb - ma;
    });

    return groups;
}

function splitHighlightsAndBody(contentLines) {
    // Extract highlights and return the body WITHOUT the highlights section
    // to avoid showing highlights twice (once in Quick Highlights box, once in body)
    const originalLines = Array.isArray(contentLines) ? contentLines : [];
    const quick = [];

    if (!originalLines.length) {
        return { highlights: quick, body: originalLines };
    }

    const lines = originalLines;

    function collectBulletsRange(startIndex) {
        // Returns {items: [], endIndex: number}
        const items = [];
        let endIndex = startIndex;
        for (let i = startIndex; i < lines.length; i++) {
            const t = lines[i].trim();
            if (!t || (!t.startsWith('- ') && !t.startsWith('* '))) {
                break;
            }
            const text = t.replace(/^[-*]\s+/, '');
            items.push(text);
            endIndex = i + 1;
        }
        return { items, endIndex };
    }

    // Helper to shorten a bullet to maxWords words.
    function shorten(text, maxWords) {
        const words = text.split(/\s+/).filter(Boolean);
        if (words.length <= maxWords) {
            return text;
        }
        return words.slice(0, maxWords).join(' ') + '…';
    }

    // Helper to remove a range from lines array
    function removeRange(arr, startIdx, endIdx) {
        return arr.filter((_, idx) => idx < startIdx || idx >= endIdx);
    }

    // Pass 1: explicit "Quick Highlights" heading - extract and remove
    for (let i = 0; i < lines.length; i++) {
        const trimmed = lines[i].trim();
        if (/^quick highlights$/i.test(trimmed)) {
            const { items, endIndex } = collectBulletsRange(i + 1);
            if (items.length) {
                items.forEach(item => quick.push(shorten(item, 7)));
            }
            // Remove the "Quick Highlights" heading and its bullets from body
            const filteredBody = removeRange(lines, i, endIndex);
            return { highlights: quick, body: filteredBody };
        }
    }

    // Pass 2: explicit "Highlights" / "Consolidated Highlights" heading - extract and remove
    for (let i = 0; i < lines.length; i++) {
        const trimmed = lines[i].trim();
        if (/^highlights$/i.test(trimmed) || /^consolidated highlights$/i.test(trimmed)) {
            const { items, endIndex } = collectBulletsRange(i + 1);
            if (items.length) {
                items.forEach(item => quick.push(shorten(item, 7)));
                // Remove the "Highlights" heading and its bullets from body
                const filteredBody = removeRange(lines, i, endIndex);
                return { highlights: quick, body: filteredBody };
            }
        }
    }

    // No explicit highlights section found - return body as-is without quick highlights
    // (Don't duplicate random bullet lists as "quick highlights")
    return { highlights: [], body: lines };
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function parseInlineMarkdown(text) {
    // First escape HTML for safety, then parse markdown
    let result = escapeHtml(text);
    // Parse bold: **text** -> <strong>text</strong>
    result = result.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    // Parse inline code: `text` -> <code>text</code>
    result = result.replace(/`([^`]+)`/g, '<code>$1</code>');
    return result;
}

function formatChangelogSections(groups) {
    let html = '<div class="changelog-sections">';

    groups.forEach((group, index) => {
        const isExpanded = index === 0; // Expand latest major version by default
        const sectionId = `changelog-section-${group.majorVersion}`;

        // Derive a simple date range for the group if dates are present
        const dates = group.sections
            .map(s => s.date)
            .filter(Boolean)
            .sort(); // ascending
        let dateLabel = '';
        if (dates.length === 1) {
            dateLabel = dates[0];
        } else if (dates.length > 1) {
            const first = dates[0];
            const last = dates[dates.length - 1];
            dateLabel = `${first} – ${last}`;
        }

        html += `
            <div class="changelog-section">
                <div class="changelog-section-header" onclick="toggleChangelogSection('${sectionId}')">
                    <div class="changelog-section-title">
                        <h3>Version ${group.majorVersion}.x</h3>
                        ${dateLabel ? `<span class="changelog-date">${escapeHtml(dateLabel)}</span>` : ''}
                    </div>
                    <div class="changelog-section-toggle">
                        <i class="fas fa-chevron-${isExpanded ? 'up' : 'down'}"></i>
                    </div>
                </div>
                <div class="changelog-section-content ${isExpanded ? 'expanded' : ''}" id="${sectionId}">
                    <div class="changelog-section-text">
                        ${group.sections.map(section => {
                            const split = splitHighlightsAndBody(section.content || []);
const highlightsHtml = split.highlights.length
                                ? `
                                    <div class="changelog-highlights">
                                        <div class="changelog-highlights-title">Quick Highlights</div>
                                        <ul>
                                            ${split.highlights.map(item => `<li>${parseInlineMarkdown(item)}</li>`).join('')}
                                        </ul>
                                    </div>
                                  `
                                : '';
                            const bodyHtml = formatChangelogContent(split.body || []);
                            return `
                                <div class="changelog-subsection">
                                    <h4>${escapeHtml(section.title)}</h4>
                                    ${section.date ? `<div class="changelog-date changelog-date-sub">${escapeHtml(section.date)}</div>` : ''}
                                    ${highlightsHtml}
                                    ${bodyHtml}
                                </div>
                            `;
                        }).join('')}
                    </div>
                </div>
            </div>
        `;
    });

    html += '</div>';
    return html;
}

function formatChangelogContent(contentLines) {
    let html = '';
    let inCodeBlock = false;
    let codeBlockContent = '';
    let inList = false;

    for (const line of contentLines) {
        if (line.startsWith('```')) {
            if (inList) {
                html += '</ul>';
                inList = false;
            }
            if (inCodeBlock) {
                // End code block
                html += `<pre><code>${escapeHtml(codeBlockContent)}</code></pre>`;
                codeBlockContent = '';
                inCodeBlock = false;
            } else {
                // Start code block
                inCodeBlock = true;
            }
        } else if (inCodeBlock) {
            codeBlockContent += line + '\n';
        } else if (line.startsWith('### ')) {
            if (inList) {
                html += '</ul>';
                inList = false;
            }
            html += `<h4>${escapeHtml(line.replace('### ', ''))}</h4>`;
        } else if (line.startsWith('## ')) {
            if (inList) {
                html += '</ul>';
                inList = false;
            }
            html += `<h3>${escapeHtml(line.replace('## ', ''))}</h3>`;
        } else if (line.startsWith('# ')) {
            if (inList) {
                html += '</ul>';
                inList = false;
            }
            html += `<h2>${escapeHtml(line.replace('# ', ''))}</h2>`;
        } else if (line.startsWith('- **')) {
            if (!inList) {
                html += '<ul>';
                inList = true;
            }
            // Bold list item
            const boldText = line.match(/\*\*(.*?)\*\*/);
            if (boldText) {
                const rest = line.replace(/- \*\*.*?\*\*/, '').trim();
                html += `<li><strong>${escapeHtml(boldText[1])}</strong>${rest ? ' ' + escapeHtml(rest) : ''}</li>`;
            } else {
                html += `<li>${escapeHtml(line.replace('- ', ''))}</li>`;
            }
        } else if (line.startsWith('- ')) {
            if (!inList) {
                html += '<ul>';
                inList = true;
            }
            html += `<li>${escapeHtml(line.replace('- ', ''))}</li>`;
        } else if (line.startsWith('**') && line.endsWith('**')) {
            if (inList) {
                html += '</ul>';
                inList = false;
            }
            html += `<strong>${escapeHtml(line.replace(/\*\*/g, ''))}</strong>`;
        } else if (line.trim() === '---') {
            if (inList) {
                html += '</ul>';
                inList = false;
            }
            html += '<hr>';
        } else if (line.trim()) {
            if (inList) {
                html += '</ul>';
                inList = false;
            }
            html += `<p>${escapeHtml(line)}</p>`;
        }
    }

    // Close any remaining code block
    if (inCodeBlock && codeBlockContent) {
        html += `<pre><code>${escapeHtml(codeBlockContent)}</code></pre>`;
    }

    if (inList) {
        html += '</ul>';
    }

    return html;
}

function toggleChangelogSection(sectionId) {
    const content = document.getElementById(sectionId);
    const header = content.previousElementSibling;
    const toggle = header.querySelector('.changelog-section-toggle i');

    if (content.classList.contains('expanded')) {
        content.classList.remove('expanded');
        toggle.className = 'fas fa-chevron-down';
    } else {
        content.classList.add('expanded');
        toggle.className = 'fas fa-chevron-up';
    }
}

async function openChangelogModal() {
    const modal = document.getElementById('changelog-modal');
    const content = document.getElementById('changelog-content');

    // Show loading state
    content.innerHTML = `
        <div class="loading-changelog">
            <div class="loading-spinner"></div>
            <p>Loading changelog...</p>
        </div>
    `;

    modal.classList.add('active');
    modal.style.display = 'flex';

    try {
        const changelogText = await loadChangelog();
        const sections = parseChangelogToSections(changelogText);
        const formattedChangelog = formatChangelogSections(sections);

        content.innerHTML = formattedChangelog;
    } catch (error) {
        content.innerHTML = `
            <div class="changelog-content">
                <div style="text-align: center; padding: 2rem; color: var(--text-secondary);">
                    <i class="fas fa-exclamation-triangle" style="font-size: 3rem; margin-bottom: 1rem;"></i>
                    <h3>Unable to Load Changelog</h3>
                    <p>There was an error loading the changelog. Please check your connection and try again.</p>
                </div>
            </div>
        `;
    }
}

function closeChangelogModal() {
    const modal = document.getElementById('changelog-modal');
    if (modal) {
        modal.classList.remove('active');
        modal.style.display = 'none';
    }
}

async function maybeShowWhatsNewModal() {
    try {
        const currentVersion = (window.APP_CONFIG && window.APP_CONFIG.version) || null;
        if (!currentVersion) {
            return;
        }

        const storageKey = 'shakshuka_last_seen_version';
        const lastSeen = localStorage.getItem(storageKey);

        // Only show if the stored version is different from the current version
        if (lastSeen === currentVersion) {
            return;
        }

        await showWhatsNewModalForLatestVersion({
            markAsSeen: true,
            storageKey
        });
    } catch (e) {
        // If anything goes wrong, just mark the current version as seen so we don't spam.
        try {
            const currentVersion = (window.APP_CONFIG && window.APP_CONFIG.version) || null;
            if (currentVersion) {
                localStorage.setItem('shakshuka_last_seen_version', currentVersion);
            }
        } catch (_) {}
    }
}

async function showWhatsNewModalForLatestVersion(options) {
    const cfg = options || {};
    const markAsSeen = !!cfg.markAsSeen;
    const storageKey = cfg.storageKey || 'shakshuka_last_seen_version';

    const currentVersion = (window.APP_CONFIG && window.APP_CONFIG.version) || null;
    const changelogText = await loadChangelog();
    const groups = parseChangelogToSections(changelogText);
    if (!Array.isArray(groups) || groups.length === 0) {
        if (markAsSeen && currentVersion) {
            localStorage.setItem(storageKey, currentVersion);
        }
        return;
    }

    const latestGroup = groups[0];
    const latestSection = latestGroup.sections && latestGroup.sections[0];
    if (!latestSection) {
        if (markAsSeen && currentVersion) {
            localStorage.setItem(storageKey, currentVersion);
        }
        return;
    }

    const split = splitHighlightsAndBody(latestSection.content || []);
    const summaryEl = document.getElementById('whats-new-summary');
    if (!summaryEl) {
        if (markAsSeen && currentVersion) {
            localStorage.setItem(storageKey, currentVersion);
        }
        return;
    }

    if (split.highlights.length) {
        summaryEl.innerHTML = `
            <ul>
                ${split.highlights.map(item => `<li>${parseInlineMarkdown(item)}</li>`).join('')}
            </ul>
        `;
    } else {
        // Fallback: show first few lines of body as plain text
        const preview = (latestSection.content || []).slice(0, 5).join(' ');
        summaryEl.textContent = preview || 'This update includes stability improvements and minor fixes.';
    }

    const modal = document.getElementById('whats-new-modal');
    if (!modal) {
        if (markAsSeen && currentVersion) {
            localStorage.setItem(storageKey, currentVersion);
        }
        return;
    }

    modal.classList.add('active');
    modal.style.display = 'flex';

    const dismiss = document.getElementById('whats-new-dismiss-btn');
    const closeBtn = document.getElementById('close-whats-new-modal');
    const viewChangelog = document.getElementById('whats-new-view-changelog-btn');

    const closeWhatsNew = () => {
        modal.classList.remove('active');
        modal.style.display = 'none';
        if (markAsSeen && currentVersion) {
            localStorage.setItem(storageKey, currentVersion);
        }
    };

    if (dismiss) dismiss.onclick = closeWhatsNew;
    if (closeBtn) closeBtn.onclick = closeWhatsNew;
    if (viewChangelog) {
        viewChangelog.onclick = async () => {
            closeWhatsNew();
            await openChangelogModal();
        };
    }
}
