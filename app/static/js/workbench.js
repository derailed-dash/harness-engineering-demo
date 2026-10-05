/**
 * Harness Engineering Workbench - Real-Time SSE Stream Controller
 */

let eventSource = null;
let startTime = null;
let timerInterval = null;
let unharnessedStartTime = null;
let harnessedStartTime = null;
let unharnessedCompleted = false;
let harnessedCompleted = false;
let unharnessedDuration = null;
let harnessedDuration = null;
let totalDuration = null;
let isReplayMode = false;
let replaySpeedMultiplier = 1.0;
let targetTotalDurationSec = null;

let unharnessedTotalTokens = 0;
let unharnessedCostUsd = 0.0;
let harnessedTotalTokens = 0;
let harnessedCostUsd = 0.0;

function updateCombinedMetrics() {
    const totalTokens = unharnessedTotalTokens + harnessedTotalTokens;
    const totalCost = unharnessedCostUsd + harnessedCostUsd;
    const totalTokensEl = document.getElementById('metric-total-tokens');
    if (totalTokensEl) totalTokensEl.innerText = totalTokens.toLocaleString();
    const totalCostEl = document.getElementById('metric-total-cost');
    if (totalCostEl) totalCostEl.innerText = `$${totalCost.toFixed(4)}`;
}

function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
}

function startTimer() {
    startTime = Date.now();
    unharnessedStartTime = Date.now();
    harnessedStartTime = Date.now();
    unharnessedCompleted = false;
    harnessedCompleted = false;
    unharnessedDuration = null;
    harnessedDuration = null;
    totalDuration = null;

    clearInterval(timerInterval);
    const intervalMs = isReplayMode ? 100 : 250;
    timerInterval = setInterval(() => {
        const now = Date.now();
        const multiplier = isReplayMode ? replaySpeedMultiplier : 1.0;

        const totalEl = document.getElementById('metric-time');
        if (totalEl) {
            if (totalDuration) {
                totalEl.innerText = totalDuration;
            } else {
                let elapsed = ((now - startTime) / 1000) * multiplier;
                if (targetTotalDurationSec && elapsed > targetTotalDurationSec) {
                    elapsed = targetTotalDurationSec;
                }
                totalEl.innerText = formatTime(elapsed);
            }
        }

        const uTimeEl = document.getElementById('unharnessed-time');
        if (uTimeEl) {
            if (unharnessedDuration) {
                uTimeEl.innerText = unharnessedDuration;
            } else if (!unharnessedCompleted && unharnessedStartTime) {
                const uElapsed = ((now - unharnessedStartTime) / 1000) * multiplier;
                uTimeEl.innerText = formatTime(uElapsed);
            }
        }

        const hTimeEl = document.getElementById('harnessed-time');
        if (hTimeEl) {
            if (harnessedDuration) {
                hTimeEl.innerText = harnessedDuration;
            } else if (!harnessedCompleted && harnessedStartTime) {
                const hElapsed = ((now - harnessedStartTime) / 1000) * multiplier;
                hTimeEl.innerText = formatTime(hElapsed);
            }
        }
    }, intervalMs);
}

function stopTimer() {
    clearInterval(timerInterval);
}

function clearFeeds() {
    unharnessedTotalTokens = 0;
    unharnessedCostUsd = 0.0;
    harnessedTotalTokens = 0;
    harnessedCostUsd = 0.0;
    unharnessedCompleted = false;
    harnessedCompleted = false;

    document.getElementById('unharnessed-feed').innerHTML = '';
    document.getElementById('harnessed-feed').innerHTML = '';
    document.getElementById('metric-time').innerText = '0:00';

    const uTokens = document.getElementById('unharnessed-tokens');
    if (uTokens) uTokens.innerText = '0';
    const uCost = document.getElementById('unharnessed-cost');
    if (uCost) uCost.innerText = '$0.0000';
    const uScore = document.getElementById('unharnessed-score');
    if (uScore) uScore.innerText = '-';
    const uTime = document.getElementById('unharnessed-time');
    if (uTime) uTime.innerText = '0:00';

    const hTokens = document.getElementById('harnessed-tokens');
    if (hTokens) hTokens.innerText = '0';
    const hCost = document.getElementById('harnessed-cost');
    if (hCost) hCost.innerText = '$0.0000';
    const hScore = document.getElementById('harnessed-score');
    if (hScore) hScore.innerText = '-';
    const hTime = document.getElementById('harnessed-time');
    if (hTime) hTime.innerText = '0:00';

    const hBadge = document.getElementById('harnessed-preview-ready');
    if (hBadge) hBadge.style.display = 'none';
    const uBadge = document.getElementById('unharnessed-preview-ready');
    if (uBadge) uBadge.style.display = 'none';

    const summaryBanner = document.getElementById('comparison-summary-banner');
    if (summaryBanner) {
        summaryBanner.style.display = 'none';
        const summaryText = document.getElementById('comparison-summary-text');
        if (summaryText) summaryText.innerText = '';
    }

    updateCombinedMetrics();
    document.querySelectorAll('.skill-tag').forEach(tag => tag.classList.remove('active'));
}


async function resetUI() {
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }
    stopTimer();
    clearFeeds();

    document.getElementById('metric-status').innerText = 'Resetting Workspaces...';
    document.getElementById('metric-status').style.color = 'var(--accent-cyan)';

    // Restore initial guidance cards
    document.getElementById('unharnessed-feed').innerHTML = `
        <div class="feed-card">
            <div class="feed-time">System Ready</div>
            <strong>Execution Strategy:</strong>
            <p style="color:#94a3b8; font-size:0.8rem; margin-top:4px;">
                Raw model prompted directly with <code>specs/cosmic_conquest_spec.md</code> in a single turn.
            </p>
            <p style="color:#64748b; font-size:0.75rem; margin-top:6px;">
                <strong>Harness Status:</strong> Zero context files (no <code>GEMINI.md</code>), no test suite generation, no linter feedback, no self-healing loop. Evaluated once at the end.
            </p>
        </div>
    `;

    document.getElementById('harnessed-feed').innerHTML = `
        <div class="feed-card">
            <div class="feed-time">System Ready</div>
            <strong>Execution Strategy:</strong>
            <p style="color:#94a3b8; font-size:0.8rem; margin-top:4px;">
                Autonomous ADK loop executing against <code>specs/cosmic_conquest_spec.md</code> with full harness engineering.
            </p>
            <p style="color:#64748b; font-size:0.75rem; margin-top:6px;">
                <strong>Harness Status:</strong> <code>GEMINI.md</code> rules (Python 3.13, PEP 585 typing, mandatory TDD) + Specialised Skills + Turn-by-turn 14-Point Rubric Gate + Living memory feedback.
            </p>
        </div>
    `;

    try {
        await fetch('/api/reset', { method: 'POST' });
    } catch (e) {
        console.error('Failed to reset backend workspaces:', e);
    }

    document.getElementById('metric-status').innerText = 'Ready';
    document.getElementById('metric-status').style.color = '#94a3b8';
    reloadPreviews(false);
}


function appendFeedCard(feedId, title, message, details = null, isHighlight = false) {
    const feed = document.getElementById(feedId);
    const card = document.createElement('div');
    card.className = 'feed-card' + (isHighlight ? ' highlight' : '');
    
    const now = new Date().toLocaleTimeString();
    let html = `<div class="feed-time">${now}</div><strong>${title}</strong><p style="margin-top:4px;">${message}</p>`;
    
    if (details) {
        html += `<pre class="code-output">${details}</pre>`;
    }
    card.innerHTML = html;
    feed.appendChild(card);
    card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function renderScorecard(feedId, scorecard) {
    const feed = document.getElementById(feedId);
    const card = document.createElement('div');
    card.className = 'feed-card highlight';
    
    const isPass = scorecard.is_passing;
    const scoreColor = isPass ? 'var(--accent-green)' : 'var(--accent-red)';
    
    let tableHtml = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <strong>Evaluation Rubric Gate</strong>
            <span style="font-size:1.2rem; font-weight:bold; color:${scoreColor}">${scorecard.score.toFixed(1)} / ${(scorecard.max_score || 14.0).toFixed(1)}</span>
        </div>
        <table class="scorecard-table">
            <thead>
                <tr><th>ID</th><th>Criterion</th><th>Result</th><th>Details</th></tr>
            </thead>
            <tbody>
    `;
    
    const allChecks = [...(scorecard.tier_1_mechanical || []), ...(scorecard.tier_2_semantic || [])];
    allChecks.forEach(c => {
        const passClass = c.passed ? 'score-pass' : 'score-fail';
        const passText = c.passed ? 'PASS' : 'FAIL';
        tableHtml += `
            <tr>
                <td><code>${c.id}</code></td>
                <td>${c.name}</td>
                <td class="${passClass}">${passText}</td>
                <td style="color:#cbd5e1; font-size:0.75rem;">${c.details}</td>
            </tr>
        `;
    });
    
    tableHtml += `</tbody></table>`;
    card.innerHTML = tableHtml;
    feed.appendChild(card);
    card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function startStream(url) {
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }
    stopTimer();
    clearFeeds();

    isReplayMode = url.includes('replay');
    replaySpeedMultiplier = isReplayMode ? 16.0 : 1.0;
    targetTotalDurationSec = null;

    startTimer();
    
    document.getElementById('metric-status').innerText = 'Running Stream...';
    document.getElementById('metric-status').style.color = 'var(--accent-cyan)';
    
    eventSource = new EventSource(url);
    
    eventSource.onmessage = (event) => {
        if (event.data === '[DONE]') {
            eventSource.close();
            stopTimer();
            document.getElementById('metric-status').innerText = 'Completed';
            document.getElementById('metric-status').style.color = 'var(--accent-green)';
            reloadPreviews(true);
            return;
        }
        
        try {
            const msg = JSON.parse(event.data);
            handleStreamEvent(msg);
        } catch (e) {
            console.error('Error parsing SSE event:', e);
        }
    };
    
    eventSource.onerror = (err) => {
        console.error('SSE Error:', err);
        eventSource.close();
        stopTimer();
        document.getElementById('metric-status').innerText = 'Stream Closed';
    };
}

function handleStreamEvent(evt) {
    if (evt.type === 'init') {
        document.getElementById('metric-status').innerText = evt.message;
        if (evt.is_replay) {
            isReplayMode = true;
            if (evt.replay_speed_multiplier) {
                replaySpeedMultiplier = evt.replay_speed_multiplier;
            }
            if (evt.total_duration_seconds) {
                targetTotalDurationSec = evt.total_duration_seconds;
            }
        }
    } else if (evt.type === 'unharnessed_event') {
        const data = evt.data;
        if (data.stage === 'starting') {
            appendFeedCard('unharnessed-feed', 'Prompt Dispatched', data.message);
        } else if (data.stage === 'generated') {
            appendFeedCard('unharnessed-feed', 'Generation Complete', data.message, data.files ? data.files.join(', ') : null);
            reloadUnharnessedPreview(true);
        } else if (data.stage === 'evaluating') {
            appendFeedCard('unharnessed-feed', 'Rubric Evaluation', data.message);
        } else if (data.stage === 'completed') {
            unharnessedCompleted = true;
            const uTimeEl = document.getElementById('unharnessed-time');
            if (data.formatted_duration) {
                unharnessedDuration = data.formatted_duration;
                if (uTimeEl) uTimeEl.innerText = data.formatted_duration;
            } else if (unharnessedStartTime) {
                const uElapsed = (Date.now() - unharnessedStartTime) / 1000;
                unharnessedDuration = formatTime(uElapsed);
                if (uTimeEl) uTimeEl.innerText = unharnessedDuration;
            }
            appendFeedCard('unharnessed-feed', 'Evaluation Verdict', data.message, null, true);
            if (data.scorecard) {
                renderScorecard('unharnessed-feed', data.scorecard);
                const uScore = document.getElementById('unharnessed-score');
                if (uScore) uScore.innerText = `${data.scorecard.score.toFixed(1)} / ${(data.scorecard.max_score || 14.0).toFixed(1)}`;
            }
            reloadUnharnessedPreview(true);
        } else if (data.stage === 'error') {
            unharnessedCompleted = true;
            const uTimeEl = document.getElementById('unharnessed-time');
            if (data.formatted_duration) {
                unharnessedDuration = data.formatted_duration;
                if (uTimeEl) uTimeEl.innerText = data.formatted_duration;
            } else if (unharnessedStartTime) {
                const uElapsed = (Date.now() - unharnessedStartTime) / 1000;
                unharnessedDuration = formatTime(uElapsed);
                if (uTimeEl) uTimeEl.innerText = unharnessedDuration;
            }
            appendFeedCard('unharnessed-feed', 'Execution Error', data.message, null, true);
            reloadUnharnessedPreview(false);
        }
        if (evt.metrics) {
            unharnessedTotalTokens = evt.metrics.total_tokens || 0;
            unharnessedCostUsd = evt.metrics.estimated_cost_usd || 0.0;
            const uTokens = document.getElementById('unharnessed-tokens');
            if (uTokens) uTokens.innerText = evt.metrics.total_tokens.toLocaleString();
            const uCost = document.getElementById('unharnessed-cost');
            if (uCost) uCost.innerText = evt.metrics.formatted_cost;
            updateCombinedMetrics();
        }
    } else if (evt.type === 'harnessed_event') {
        const data = evt.data;
        if (data.stage === 'starting') {
            appendFeedCard('harnessed-feed', 'Harness Initialised', data.message);
        } else if (data.stage === 'skill_activated') {
            appendFeedCard('harnessed-feed', `Skill Activated: ${data.name}`, data.message, `Rationale: ${data.rationale}`);
            const tagMap = {
                'test-driven-development': 'skill-tag-tdd',
                'api-and-interface-design': 'skill-tag-api',
                'gemini-api-dev': 'skill-tag-gemini',
            };
            const tagId = tagMap[data.skill];
            if (tagId) {
                const el = document.getElementById(tagId);
                if (el) el.classList.add('active');
            }
        } else if (data.stage === 'iteration_start') {
            appendFeedCard('harnessed-feed', `Iteration ${data.iteration} Started`, data.message, null, true);
            reloadHarnessedPreview(false);
        } else if (data.tool_exec) {
            appendFeedCard('harnessed-feed', `Tool Execution: ${data.tool}`, data.message, data.output);
        } else if (data.stage === 'tool_exec') {
            appendFeedCard('harnessed-feed', `Tool Execution: ${data.tool}`, data.message, data.output);
        } else if (data.stage === 'living_memory') {
            appendFeedCard('harnessed-feed', `Living Memory Feedback`, data.message, data.diagnostics);
        } else if (data.stage === 'rubric_update' && data.scorecard) {
            renderScorecard('harnessed-feed', data.scorecard);
            const hScore = document.getElementById('harnessed-score');
            if (hScore) hScore.innerText = `${data.scorecard.score.toFixed(1)} / ${(data.scorecard.max_score || 14.0).toFixed(1)}`;
            reloadHarnessedPreview(true);
        } else if (data.stage === 'completed') {
            harnessedCompleted = true;
            const hTimeEl = document.getElementById('harnessed-time');
            if (data.formatted_duration) {
                harnessedDuration = data.formatted_duration;
                if (hTimeEl) hTimeEl.innerText = data.formatted_duration;
            } else if (harnessedStartTime) {
                const hElapsed = (Date.now() - harnessedStartTime) / 1000;
                harnessedDuration = formatTime(hElapsed);
                if (hTimeEl) hTimeEl.innerText = harnessedDuration;
            }
            appendFeedCard('harnessed-feed', 'Harness Gate Passed', data.message, null, true);
            if (data.scorecard) {
                renderScorecard('harnessed-feed', data.scorecard);
                const hScore = document.getElementById('harnessed-score');
                if (hScore) hScore.innerText = `${data.scorecard.score.toFixed(1)} / ${(data.scorecard.max_score || 14.0).toFixed(1)}`;
            }
            reloadHarnessedPreview(true);
        } else if (data.stage === 'error') {
            harnessedCompleted = true;
            const hTimeEl = document.getElementById('harnessed-time');
            if (data.formatted_duration) {
                harnessedDuration = data.formatted_duration;
                if (hTimeEl) hTimeEl.innerText = data.formatted_duration;
            } else if (harnessedStartTime) {
                const hElapsed = (Date.now() - harnessedStartTime) / 1000;
                harnessedDuration = formatTime(hElapsed);
                if (hTimeEl) hTimeEl.innerText = harnessedDuration;
            }
            appendFeedCard('harnessed-feed', 'Execution Error', data.message, null, true);
            reloadHarnessedPreview(false);
        }
        if (evt.metrics) {
            harnessedTotalTokens = evt.metrics.total_tokens || 0;
            harnessedCostUsd = evt.metrics.estimated_cost_usd || 0.0;
            const hTokens = document.getElementById('harnessed-tokens');
            if (hTokens) hTokens.innerText = evt.metrics.total_tokens.toLocaleString();
            const hCost = document.getElementById('harnessed-cost');
            if (hCost) hCost.innerText = evt.metrics.formatted_cost;
            updateCombinedMetrics();
        }
    } else if (evt.type === 'comparison_summary') {
        stopTimer();
        if (evt.total_formatted_duration) {
            totalDuration = evt.total_formatted_duration;
            const totalEl = document.getElementById('metric-time');
            if (totalEl) totalEl.innerText = evt.total_formatted_duration;
        }
        if (evt.unharnessed_formatted_duration) {
            unharnessedDuration = evt.unharnessed_formatted_duration;
            const uTimeEl = document.getElementById('unharnessed-time');
            if (uTimeEl) uTimeEl.innerText = evt.unharnessed_formatted_duration;
        }
        if (evt.harnessed_formatted_duration) {
            harnessedDuration = evt.harnessed_formatted_duration;
            const hTimeEl = document.getElementById('harnessed-time');
            if (hTimeEl) hTimeEl.innerText = evt.harnessed_formatted_duration;
        }

        // Display unified comparison summary in full-width banner across both tracks
        const banner = document.getElementById('comparison-summary-banner');
        const summaryText = document.getElementById('comparison-summary-text');
        const summaryTime = document.getElementById('comparison-summary-time');
        if (banner && summaryText) {
            summaryText.innerText = evt.message;
            if (summaryTime) {
                summaryTime.innerText = new Date().toLocaleTimeString();
            }
            banner.style.display = 'flex';
            banner.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }
}

function reloadHarnessedPreview(showBadge = false) {
    const harnessedFrame = document.getElementById('frame-harnessed');
    if (harnessedFrame) {
        const url = `/preview/harnessed?t=${Date.now()}`;
        harnessedFrame.src = url;
        try {
            if (harnessedFrame.contentWindow && harnessedFrame.contentWindow.location) {
                harnessedFrame.contentWindow.location.replace(url);
            }
        } catch (e) {
            // cross-origin guard
        }
    }
    if (showBadge) {
        const badge = document.getElementById('harnessed-preview-ready');
        if (badge) badge.style.display = 'inline-flex';
    }
}

function reloadUnharnessedPreview(showBadge = false) {
    const unharnessedFrame = document.getElementById('frame-unharnessed');
    if (unharnessedFrame) {
        const url = `/preview/unharnessed?t=${Date.now()}`;
        unharnessedFrame.src = url;
        try {
            if (unharnessedFrame.contentWindow && unharnessedFrame.contentWindow.location) {
                unharnessedFrame.contentWindow.location.replace(url);
            }
        } catch (e) {
            // cross-origin guard
        }
    }
    if (showBadge) {
        const badge = document.getElementById('unharnessed-preview-ready');
        if (badge) badge.style.display = 'inline-flex';
    }
}

function reloadPreviews(showBadge = false) {
    reloadUnharnessedPreview(showBadge);
    reloadHarnessedPreview(showBadge);
}

function switchTab(tabId) {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.preview-frame').forEach(frame => frame.style.display = 'none');
    
    const openLink = document.getElementById('btn-open-preview-tab');

    if (tabId === 'harnessed') {
        document.getElementById('tab-btn-harnessed').classList.add('active');
        const frame = document.getElementById('frame-harnessed');
        if (frame) frame.style.display = 'block';
        if (openLink) {
            openLink.href = '/preview/harnessed';
            openLink.style.color = 'var(--accent-cyan)';
            openLink.innerHTML = '<i class="fa-solid fa-arrow-up-right-from-square"></i> Open Harnessed Game in New Tab';
        }
        reloadHarnessedPreview(false);
    } else {
        document.getElementById('tab-btn-unharnessed').classList.add('active');
        const frame = document.getElementById('frame-unharnessed');
        if (frame) frame.style.display = 'block';
        if (openLink) {
            openLink.href = '/preview/unharnessed';
            openLink.style.color = 'var(--accent-red)';
            openLink.innerHTML = '<i class="fa-solid fa-arrow-up-right-from-square"></i> Open Unharnessed Game in New Tab';
        }
        reloadUnharnessedPreview(false);
    }
}

// Initial preview load & specification rendering
window.addEventListener('DOMContentLoaded', () => {
    reloadPreviews(false);
    initSpecContent();
});

// ============================================================================
// Document Viewer Modal Controller (Shared Spec & Harness Context)
// ============================================================================

let currentDocType = 'spec'; // 'spec' | 'harness_context'
let currentSpecViewMode = 'rendered'; // 'rendered' | 'raw'

const DOC_CONFIGS = {
    spec: {
        title: 'specs/cosmic_conquest_spec.md',
        subtitle: 'Shared Goal Specification (Identical Baseline for Both Pipelines)',
        iconClass: 'fa-regular fa-file-lines modal-icon',
        dataId: 'spec-content-data',
        footerNote: '<i class="fa-solid fa-circle-info" style="color:var(--accent-cyan);"></i> Both the Unharnessed and Harnessed agents receive this exact same specification. The only variable is the Harness.',
    },
    harness_context: {
        title: 'harness/harness_context.md',
        subtitle: 'Harness Engineering Context & Guardrails (Injected only into Harnessed Pipeline)',
        iconClass: 'fa-solid fa-file-shield modal-icon',
        dataId: 'harness-context-data',
        footerNote: '<i class="fa-solid fa-shield-halved" style="color:var(--accent-green);"></i> Persistent workspace instructions (GEMINI.md) defining PEP 585 typing, mandatory TDD, Pydantic contracts, and UI wiring.',
    },

    'test-driven-development': {
        title: 'harness/skills/test-driven-development/SKILL.md',
        subtitle: 'Specialised Skill: Test-Driven Development (TDD)',
        iconClass: 'fa-solid fa-flask modal-icon',
        dataId: 'skill-content-test-driven-development',
        footerNote: '<i class="fa-solid fa-flask" style="color:var(--accent-cyan);"></i> Externalised skill instructing the agent to author tests before code in tests/test_game.py.',
    },
    'api-and-interface-design': {
        title: 'harness/skills/api-and-interface-design/SKILL.md',
        subtitle: 'Specialised Skill: API & Interface Design',
        iconClass: 'fa-solid fa-code modal-icon',
        dataId: 'skill-content-api-and-interface-design',
        footerNote: '<i class="fa-solid fa-code" style="color:var(--accent-cyan);"></i> Externalised skill enforcing Pydantic models, request validation, and HTTP 400 rejection contracts.',
    },
    'gemini-api-dev': {
        title: 'harness/skills/gemini-api-dev/SKILL.md',
        subtitle: 'Specialised Skill: Gemini API Development',
        iconClass: 'fa-solid fa-brain modal-icon',
        dataId: 'skill-content-gemini-api-dev',
        footerNote: '<i class="fa-solid fa-brain" style="color:var(--accent-cyan);"></i> Externalised skill providing google-genai SDK guidance, structured outputs, and domain grounding.',
    },
};


function handleSpecModalKeydown(event) {
    if (event.key === 'Escape') {
        closeSpecModal();
    }
}

function handleModalBackdropClick(event) {
    if (event.target && event.target.id === 'spec-modal') {
        closeSpecModal();
    }
}

function displayDocument(docType) {
    currentDocType = docType || 'spec';
    const config = DOC_CONFIGS[currentDocType] || DOC_CONFIGS.spec;

    const titleEl = document.getElementById('modal-spec-title');
    const subtitleEl = document.getElementById('modal-spec-subtitle');
    const iconEl = document.getElementById('modal-doc-icon');
    const footerNoteEl = document.getElementById('modal-footer-note');
    const dataEl = document.getElementById(config.dataId);
    const rawCodeEl = document.getElementById('spec-raw-code');
    const renderedView = document.getElementById('spec-rendered-view');

    if (titleEl) titleEl.innerText = config.title;
    if (subtitleEl) subtitleEl.innerText = config.subtitle;
    if (iconEl) iconEl.className = config.iconClass;
    if (footerNoteEl) footerNoteEl.innerHTML = config.footerNote;

    let markdownText = (dataEl ? dataEl.textContent : '') || '';

    // Guard against any lingering HTML entity encoding (e.g. &#34;, &quot;)
    if (markdownText.includes('&')) {
        const parser = new DOMParser();
        const doc = parser.parseFromString(markdownText, 'text/html');
        markdownText = doc.documentElement.textContent || markdownText;
    }

    if (rawCodeEl) {
        rawCodeEl.textContent = markdownText;
    }

    if (renderedView) {
        if (typeof marked !== 'undefined' && typeof marked.parse === 'function') {
            renderedView.innerHTML = marked.parse(markdownText);
        } else {
            renderedView.innerHTML = `<pre style="white-space:pre-wrap; font-family:monospace; color:#cbd5e1;">${escapeHtml(markdownText)}</pre>`;
        }
    }

    applySpecViewMode();
}

function initSpecContent() {
    displayDocument('spec');
}

function openSpecModal() {
    displayDocument('spec');
    const modal = document.getElementById('spec-modal');
    if (!modal) return;

    modal.classList.add('open');
    window.addEventListener('keydown', handleSpecModalKeydown);
}

function openHarnessContextModal() {
    displayDocument('harness_context');
    const modal = document.getElementById('spec-modal');
    if (!modal) return;

    modal.classList.add('open');
    window.addEventListener('keydown', handleSpecModalKeydown);
}

function openSkillModal(skillName) {
    displayDocument(skillName);
    const modal = document.getElementById('spec-modal');
    if (!modal) return;

    modal.classList.add('open');
    window.addEventListener('keydown', handleSpecModalKeydown);
}

function openDocModal(docType) {
    if (docType === 'harness_context') {
        openHarnessContextModal();
    } else if (docType in DOC_CONFIGS) {
        openSkillModal(docType);
    } else {
        openSpecModal();
    }
}


function applySpecViewMode() {
    const renderedView = document.getElementById('spec-rendered-view');
    const rawView = document.getElementById('spec-raw-view');
    const toggleBtn = document.getElementById('spec-toggle-view-btn');

    if (currentSpecViewMode === 'rendered') {
        if (renderedView) renderedView.style.display = 'block';
        if (rawView) rawView.style.display = 'none';
        if (toggleBtn) {
            toggleBtn.innerHTML = '<i class="fa-solid fa-code"></i> <span>Raw Markdown</span>';
            toggleBtn.classList.remove('active');
        }
    } else {
        if (renderedView) renderedView.style.display = 'none';
        if (rawView) rawView.style.display = 'block';
        if (toggleBtn) {
            toggleBtn.innerHTML = '<i class="fa-solid fa-file-lines"></i> <span>Rendered View</span>';
            toggleBtn.classList.add('active');
        }
    }
}

function toggleSpecViewMode() {
    currentSpecViewMode = currentSpecViewMode === 'rendered' ? 'raw' : 'rendered';
    applySpecViewMode();
}

function closeSpecModal() {
    const modal = document.getElementById('spec-modal');
    if (modal) modal.classList.remove('open');
    window.removeEventListener('keydown', handleSpecModalKeydown);
}

function escapeHtml(str) {
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
