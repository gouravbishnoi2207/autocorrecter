console.debug('[script.js] loaded');
document.addEventListener('DOMContentLoaded', () => {
  console.debug('[script.js] DOMContentLoaded');
  setupThemeToggle();
            setupAdminDashboard();

            const inputText = document.getElementById('inputText');
            if (!inputText) {
                setupHistoryPage();
                return;
            }

            const languageSelect = document.getElementById('languageSelect');
            const correctBtn = document.getElementById('correctBtn');
            const previewBtn = document.getElementById('previewBtn');
            const clearBtn = document.getElementById('clearBtn');
            const voiceBtn = document.getElementById('voiceBtn');
            const messageBox = document.getElementById('messageBox');
            const statWords = document.getElementById('statWords');
            const statIncorrect = document.getElementById('statIncorrect');
            const statCorrections = document.getElementById('statCorrections');
            const statAccuracy = document.getElementById('statAccuracy');
            const confidenceScore = document.getElementById('confidenceScore');
            const readabilityScore = document.getElementById('readabilityScore');
            const sentimentScore = document.getElementById('sentimentScore');
            const keywordsScore = document.getElementById('keywordsScore');
            const originalPreview = document.getElementById('originalPreview');
            const correctedPreview = document.getElementById('correctedPreview');
            const diffPreview = document.getElementById('diffPreview');
            const suggestionsPreview = document.getElementById('suggestionsPreview');
            const explanationsPreview = document.getElementById('explanationsPreview');

            const state = { timer: null };
            let recognition = null;

            setEmptyState();

            inputText.addEventListener('input', () => {
                clearTimeout(state.timer);
                state.timer = setTimeout(() => refreshPreview(), 450);
            });

            if (correctBtn) correctBtn.addEventListener('click', () => submitText('/api/correct'));
            if (previewBtn) previewBtn.addEventListener('click', () => refreshPreview());
            if (clearBtn) clearBtn.addEventListener('click', clearEditor);
            if (voiceBtn) voiceBtn.addEventListener('click', toggleVoiceInput);
            console.debug('[script.js] main handlers attached', {
              correct: !!correctBtn,
              preview: !!previewBtn,
              clear: !!clearBtn,
              voice: !!voiceBtn,
            });

            function setupThemeToggle() {
                const toggle = document.getElementById('themeToggle');
                if (!toggle) return;

                const savedTheme = localStorage.getItem('ai-autocorrect-theme') || 'dark';
                applyTheme(savedTheme);

                toggle.addEventListener('click', () => {
                    const nextTheme = document.body.classList.contains('light-mode') ? 'dark' : 'light';
                    applyTheme(nextTheme);
                    localStorage.setItem('ai-autocorrect-theme', nextTheme);
                });
            }

            function applyTheme(theme) {
                const isLight = theme === 'light';
                document.body.classList.toggle('light-mode', isLight);
                document.body.classList.toggle('dark-mode', !isLight);
            }

            function setEmptyState() {
                if (originalPreview) originalPreview.textContent = 'Your raw text will appear here.';
                if (correctedPreview) correctedPreview.textContent = 'Your improved text will appear here.';
                if (diffPreview) diffPreview.textContent = 'Corrections will be highlighted here.';
                if (suggestionsPreview) suggestionsPreview.innerHTML = '';
                if (explanationsPreview) explanationsPreview.innerHTML = '';
                setStats({ total_words: 0, incorrect_words_found: 0, corrections_applied: 0, accuracy_percentage: 100, confidence_score: 0, readability_score: 0 },
                    'Neutral', [],
                );
            }

            function clearEditor() {
                inputText.value = '';
                setEmptyState();
                showMessage('Editor cleared.', 'info');
            }

function toggleVoiceInput() {
    const SpeechRecognition =
        window.SpeechRecognition ||
        window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
        showMessage(
            'Speech recognition is not supported in this browser. Please use Chrome or Edge.',
            'warning'
        );
        return;
    }

    // Stop listening if already active
    if (recognition) {
        recognition.stop();
        recognition = null;
        showMessage('Voice input stopped.', 'info');
        return;
    }

    recognition = new SpeechRecognition();

    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.maxAlternatives = 1;

    const voiceLanguages = {
        en: 'en-US',
        es: 'es-ES',
        fr: 'fr-FR',
        de: 'de-DE',
        pt: 'pt-BR',
        it: 'it-IT',
        nl: 'nl-NL'
    };

    const selectedLanguage =
        languageSelect ? languageSelect.value : 'en';

    recognition.lang =
        voiceLanguages[selectedLanguage] || 'en-US';

    recognition.onstart = () => {
        if (voiceBtn) {
            voiceBtn.innerHTML =
                '<i class="bi bi-stop-circle"></i> Stop Listening';

            voiceBtn.classList.remove('btn-outline-info');
            voiceBtn.classList.add('btn-danger');
        }

        showMessage(
            'Listening... Speak now.',
            'info'
        );
    };

    recognition.onresult = (event) => {
        let finalTranscript = '';
        let interimTranscript = '';

        for (
            let index = event.resultIndex;
            index < event.results.length;
            index += 1
        ) {
            const transcript =
                event.results[index][0].transcript;

            if (event.results[index].isFinal) {
                finalTranscript += transcript;
            } else {
                interimTranscript += transcript;
            }
        }

        // Put the final/interim speech into the editor
        const spokenText =
            `${finalTranscript} ${interimTranscript}`.trim();

        if (spokenText) {
            inputText.value =
                `${inputText.value} ${spokenText}`.trim();
        }
    };

    recognition.onerror = (event) => {
        console.error(
            'Speech recognition error:',
            event.error
        );

        if (event.error === 'not-allowed') {
            showMessage(
                'Microphone permission was denied. Please allow microphone access.',
                'warning'
            );
        } else if (event.error === 'no-speech') {
            showMessage(
                'No speech detected. Please try speaking again.',
                'warning'
            );
        } else if (event.error === 'audio-capture') {
            showMessage(
                'No microphone was detected.',
                'warning'
            );
        } else {
            showMessage(
                `Voice input error: ${event.error}`,
                'warning'
            );
        }
    };

    recognition.onend = () => {
        if (voiceBtn) {
            voiceBtn.innerHTML =
                '<i class="bi bi-mic-fill"></i> Voice Input';

            voiceBtn.classList.remove('btn-danger');
            voiceBtn.classList.add('btn-outline-info');
        }

        recognition = null;

        // Analyze only after speech recognition finishes
        if (inputText.value.trim()) {
            refreshPreview();
        }
    };

    try {
        recognition.start();

        showMessage(
            'Listening for speech input...',
            'info'
        );
    } catch (error) {
        console.error(
            'Could not start speech recognition:',
            error
        );

        recognition = null;

        showMessage(
            'Unable to start voice input. Please try again.',
            'danger'
        );
    }
}

            async function submitText(endpoint) {
                const payload = getPayload();
                if (!payload.text.trim()) {
                    showMessage('Please enter text to analyze.', 'warning');
                    return;
                }

                setBusy(true);
                try {
                    const response = await fetch(endpoint, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload),
                    });
                    const data = await response.json();
                    if (!response.ok) {
                        throw new Error(data.message || 'Unable to process text.');
                    }
                    renderResult(data);
                    showMessage(data.stored ? 'Text corrected and saved to history.' : 'Preview updated.', 'success');
                } catch (error) {
                    showMessage(error.message, 'danger');
                } finally {
                    setBusy(false);
                }
            }

            async function refreshPreview() {
                const payload = getPayload();
                if (!payload.text.trim()) {
                    setEmptyState();
                    return;
                }

                try {
                    const response = await fetch('/api/preview', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload),
                    });
                    const data = await response.json();
                    if (!response.ok) {
                        throw new Error(data.message || 'Unable to preview text.');
                    }
                    renderResult(data);
                } catch (error) {
                    showMessage(error.message, 'warning');
                }
            }

            function renderResult(data) {
                const stats = data.stats || {};
                setStats(stats, data.sentiment_label || 'Neutral', data.keywords || []);

                if (originalPreview) originalPreview.innerHTML = data.diff_html?.original || escapeHtml(data.original_text || '');
                if (correctedPreview) correctedPreview.innerHTML = data.diff_html?.corrected || escapeHtml(data.corrected_text || '');
                if (diffPreview) diffPreview.innerHTML = buildComparisonCard(data);
                if (suggestionsPreview) suggestionsPreview.innerHTML = buildSuggestions(data);
                if (explanationsPreview) explanationsPreview.innerHTML = buildExplanations(data);
            }

            function buildComparisonCard(data) {
                const readability = data.readability_score ?? 0;
                const confidence = data.confidence_score ?? 0;
                return `
      <div class="mb-2"><strong>Readability score:</strong> ${formatNumber(readability)} / 100</div>
      <div class="mb-2"><strong>Confidence:</strong> ${formatNumber(confidence)}%</div>
      <div>${data.diff_html?.original ? data.diff_html.original : escapeHtml(data.original_text || '')}</div>
      <hr class="border-secondary-subtle my-3">
      <div>${data.diff_html?.corrected ? data.diff_html.corrected : escapeHtml(data.corrected_text || '')}</div>
    `;
            }

            function buildSuggestions(data) {
                const corrections = data.corrections || [];
                const keywords = data.keywords || [];
                const parts = [];

                if (corrections.length === 0) {
                    parts.push('<p class="text-secondary mb-3">No corrections were needed.</p>');
                } else {
                    corrections.slice(0, 6).forEach((item) => {
                                parts.push(`
          <div class="explanation-card">
            <div class="fw-semibold">${escapeHtml(item.original || '')} → ${escapeHtml(item.corrected || '')}</div>
            <small>${escapeHtml((item.reason || '').toString())}</small>
            <div class="mt-2">
              ${(item.suggestions || []).map((suggestion) => `<span class="suggestion-pill">${escapeHtml(suggestion)}</span>`).join('')}
            </div>
          </div>
        `);
      });
    }

    if (keywords.length) {
      parts.push(`<div class="mt-3"><div class="fw-semibold mb-2">Keywords</div>${keywords.map((keyword) => `<span class="keyword-pill">${escapeHtml(keyword)}</span>`).join('')}</div>`);
    }

    return parts.join('');
  }

  function buildExplanations(data) {
    const explanations = data.explanations || [];
    if (!explanations.length) {
      return '<p class="text-secondary mb-0">No explanation needed for the current text.</p>';
    }

    return explanations.slice(0, 8).map((item) => `
      <div class="explanation-card">
        <div class="fw-semibold mb-1">${escapeHtml(item.type || 'Correction')}</div>
        <div class="mb-1"><strong>Why it was incorrect:</strong> ${escapeHtml(item.reason || '')}</div>
        <div class="mb-1"><strong>Why it is better:</strong> ${escapeHtml(item.better_choice || '')}</div>
        <div class="mb-2"><strong>Confidence:</strong> ${formatNumber(item.confidence || 0)}%</div>
      </div>
    `).join('');
  }

  function setStats(stats, sentiment, keywords) {
    if (statWords) statWords.textContent = stats.total_words ?? 0;
    if (statIncorrect) statIncorrect.textContent = stats.incorrect_words_found ?? 0;
    if (statCorrections) statCorrections.textContent = stats.corrections_applied ?? 0;
    if (statAccuracy) statAccuracy.textContent = `${formatNumber(stats.accuracy_percentage ?? 100)}%`;
    if (confidenceScore) confidenceScore.textContent = `${formatNumber(stats.confidence_score ?? 0)}%`;
    if (readabilityScore) readabilityScore.textContent = formatNumber(stats.readability_score ?? 0);
    if (sentimentScore) sentimentScore.textContent = sentiment || 'Neutral';
    if (keywordsScore) keywordsScore.textContent = Array.isArray(keywords) && keywords.length ? keywords.join(', ') : '-';
  }

  function setBusy(isBusy) {
    [correctBtn, previewBtn, clearBtn, voiceBtn].forEach((button) => {
      if (button) button.disabled = isBusy;
    });
  }

  function getPayload() {
    return {
      text: inputText.value,
      language: languageSelect ? languageSelect.value : 'en',
      context_before: getContextBeforeCursor(inputText),
    };
  }

  function getContextBeforeCursor(textarea) {
    const cursor = textarea.selectionStart || textarea.value.length;
    const beforeCursor = textarea.value.slice(0, cursor).trim();
    const sentences = beforeCursor.split(/(?<=[.!?])\s+/).filter(Boolean);
    return sentences.slice(-2).join(' ');
  }

  function showMessage(message, type = 'info') {
    if (!messageBox) return;
    messageBox.className = `alert alert-${type}`;
    messageBox.textContent = message;
    messageBox.classList.remove('d-none');
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function formatNumber(value) {
    const numeric = Number.parseFloat(value || 0);
    return Number.isInteger(numeric) ? String(numeric) : numeric.toFixed(2).replace(/\.00$/, '');
  }

  function setupHistoryPage() {
    const buttons = document.querySelectorAll('.view-detail-btn');
    if (!buttons.length) return;

    const modalElement = document.getElementById('detailModal');
    const modal = modalElement ? new bootstrap.Modal(modalElement) : null;
    const detailLoading = document.getElementById('detailLoading');
    const detailContent = document.getElementById('detailContent');
    const detailOriginal = document.getElementById('detailOriginal');
    const detailCorrected = document.getElementById('detailCorrected');
    const detailStats = document.getElementById('detailStats');
    const detailExplanations = document.getElementById('detailExplanations');

    buttons.forEach((button) => {
      button.addEventListener('click', async () => {
        const recordId = button.dataset.historyId;
        if (!modal) return;
        modal.show();
        if (detailLoading) detailLoading.classList.remove('d-none');
        if (detailContent) detailContent.classList.add('d-none');

        try {
          const response = await fetch(`/api/history/${recordId}`);
          const data = await response.json();
          if (!response.ok) throw new Error(data.message || 'Unable to load history item.');

          const item = data.item || {};
          if (detailOriginal) detailOriginal.innerHTML = escapeHtml(item.original_text || '');
          if (detailCorrected) detailCorrected.innerHTML = escapeHtml(item.corrected_text || '');
          if (detailStats) detailStats.textContent = JSON.stringify(item.stats || {}, null, 2);
          if (detailExplanations) detailExplanations.textContent = JSON.stringify(item.explanations || [], null, 2);
          if (detailLoading) detailLoading.classList.add('d-none');
          if (detailContent) detailContent.classList.remove('d-none');
        } catch (error) {
          if (detailLoading) detailLoading.textContent = error.message;
        }
      });
    });
  }

  function setupAdminDashboard() {
    if (!window.__DASHBOARD__) return;

    const dashboard = window.__DASHBOARD__;
    const activityCanvas = document.getElementById('activityChart');
    const languageCanvas = document.getElementById('languageChart');
    const modeCanvas = document.getElementById('modeChart');
    if (!activityCanvas || !languageCanvas || !modeCanvas || typeof Chart === 'undefined') return;

    new Chart(activityCanvas, {
      type: 'line',
      data: {
        labels: dashboard.activity_labels || [],
        datasets: [{
          label: 'Corrections',
          data: dashboard.activity_values || [],
          borderColor: '#39d0ff',
          backgroundColor: 'rgba(57, 208, 255, 0.12)',
          fill: true,
          tension: 0.35,
        }],
      },
      options: {
        responsive: true,
        plugins: { legend: { labels: { color: '#eaf1ff' } } },
        scales: {
          x: { ticks: { color: '#9caecf' }, grid: { color: 'rgba(148, 172, 209, 0.12)' } },
          y: { ticks: { color: '#9caecf' }, grid: { color: 'rgba(148, 172, 209, 0.12)' } },
        },
      },
    });

    new Chart(languageCanvas, {
      type: 'doughnut',
      data: {
        labels: (dashboard.language_distribution || []).map((item) => item.label),
        datasets: [{
          data: (dashboard.language_distribution || []).map((item) => item.value),
          backgroundColor: ['#39d0ff', '#7c5cff', '#18d6a4', '#ff6d7a', '#ffd166', '#6ea8fe'],
        }],
      },
      options: {
        plugins: { legend: { position: 'bottom', labels: { color: '#eaf1ff' } } },
      },
    });

    new Chart(modeCanvas, {
      type: 'bar',
      data: {
        labels: (dashboard.analysis_mode_distribution || []).map((item) => item.label),
        datasets: [{
          label: 'Mode usage',
          data: (dashboard.analysis_mode_distribution || []).map((item) => item.value),
          backgroundColor: '#7c5cff',
        }],
      },
      options: {
        plugins: { legend: { labels: { color: '#eaf1ff' } } },
        scales: {
          x: { ticks: { color: '#9caecf' }, grid: { color: 'rgba(148, 172, 209, 0.12)' } },
          y: { ticks: { color: '#9caecf' }, grid: { color: 'rgba(148, 172, 209, 0.12)' } },
        },
      },
    });
  }
});
