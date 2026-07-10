(function () {
  const eventIdEl = document.getElementById('event-id');
  const sessionIdEl = document.getElementById('session-id');
  if (!eventIdEl || !sessionIdEl) return; // no event/session selected yet

  const EVENT_ID = JSON.parse(eventIdEl.textContent);
  const SESSION_ID = JSON.parse(sessionIdEl.textContent);
  if (!EVENT_ID || !SESSION_ID) return;

  const SCAN_URL = '/dashboard/attendance/scan/';

  let checkType = 'check_in';
  let scanning = false;
  let lastScanAt = 0;
  const SCAN_COOLDOWN_MS = 2500; // prevent the same camera frame re-triggering instantly

  function getCookie(name) {
    const match = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
    return match ? match.pop() : '';
  }

  // ---------------------------------------------------------------- Audio
  function beep(kind) {
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      const ctx = new AudioCtx();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.type = 'sine';
      if (kind === 'success') {
        osc.frequency.value = 880;
        gain.gain.setValueAtTime(0.15, ctx.currentTime);
        osc.start();
        osc.stop(ctx.currentTime + 0.12);
      } else {
        osc.frequency.value = 220;
        gain.gain.setValueAtTime(0.15, ctx.currentTime);
        osc.start();
        osc.stop(ctx.currentTime + 0.28);
      }
      osc.onended = () => ctx.close();
    } catch (e) { /* audio not available, ignore */ }
  }

  // ------------------------------------------------------------- Check-type toggle
  const toggle = document.getElementById('checktype-toggle');
  if (toggle) {
    toggle.addEventListener('click', function (e) {
      const btn = e.target.closest('button');
      if (!btn) return;
      toggle.querySelectorAll('button').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      checkType = btn.dataset.value;
    });
  }

  // ------------------------------------------------------------- Offline detection
  const offlineBanner = document.getElementById('offline-banner');
  function updateOnlineState() {
    if (!offlineBanner) return;
    offlineBanner.classList.toggle('is-visible', !navigator.onLine);
  }
  window.addEventListener('online', updateOnlineState);
  window.addEventListener('offline', updateOnlineState);
  updateOnlineState();

  // ------------------------------------------------------------- Result rendering
  const resultPanel = document.getElementById('scan-result-panel');
  const recentList = document.getElementById('recent-scans-list');
  const countedIn = document.querySelector('.scan-count:nth-child(1) .n');
  const countedOut = document.querySelector('.scan-count:nth-child(2) .n');

  function initials(name) {
    return (name || '').split(' ').filter(Boolean).slice(0, 2).map(s => s[0].toUpperCase()).join('');
  }

  function bannerClass(data) {
    if (data.ok) return 'success';
    if (data.is_warning) return 'warning';
    return 'error';
  }

  function renderResult(data) {
    const cls = bannerClass(data);
    let html = `<div class="scan-status-banner ${cls}">${data.message}</div>`;

    if (data.person) {
      const p = data.person;
      const avatar = p.photo_url
        ? `<img class="avatar-lg" src="${p.photo_url}" alt="">`
        : `<div class="avatar avatar-lg">${initials(p.full_name)}</div>`;
      html += `
        <div class="scan-result-card">
          ${avatar}
          <div style="min-width:0">
            <div style="font-weight:600;font-size:15px">${p.full_name}</div>
            <div class="text-muted" style="font-size:12px;margin-bottom:8px">${p.person_id}${p.registration_number ? ' · ' + p.registration_number : ''}</div>
            ${p.category ? `<span class="pill ${p.category === 'Worker' ? 'pill-worker' : 'pill-participant'}">${p.category}${p.worker_type ? ' · ' + p.worker_type : ''}</span>` : ''}
            ${p.department ? `<div class="text-muted" style="font-size:12px;margin-top:6px">${p.department}</div>` : ''}
          </div>
        </div>`;
    }

    if (data.recent_attendance && data.recent_attendance.length) {
      html += `<div style="margin-top:14px;border-top:1px solid var(--border-subtle);padding-top:10px">
        <div class="text-muted" style="font-size:11px;text-transform:uppercase;letter-spacing:.04em;margin-bottom:6px">Recent activity</div>`;
      data.recent_attendance.forEach(a => {
        html += `<div class="row-item" style="padding:6px 0">
          <div class="row-item-sub">${a.session_label}</div>
          <div class="row-item-meta">${a.check_type} · ${a.scanned_at}</div>
        </div>`;
      });
      html += `</div>`;
    }

    resultPanel.innerHTML = html;
  }

  function prependRecentScan(a, personName, personId, checkTypeLabel) {
    if (!recentList) return;
    const empty = recentList.querySelector('.empty-state');
    if (empty) empty.remove();
    const initialsTxt = (personName || '').split(' ').filter(Boolean).slice(0, 2).map(s => s[0].toUpperCase()).join('');
    const pillClass = a.check_type === 'Check-in' ? 'pill-participant' : 'pill-worker';
    const row = document.createElement('div');
    row.className = 'row-item';
    row.innerHTML = `
      <div class="row-item-main">
        <div class="avatar" style="width:28px;height:28px;font-size:11px">${initialsTxt}</div>
        <div style="min-width:0">
          <div class="row-item-title">${personName}</div>
          <div class="row-item-sub">${personId}</div>
        </div>
      </div>
      <div class="row-item-meta">
        <span class="pill ${pillClass}">${a.check_type}</span>
        <div style="margin-top:4px">${a.scanned_at.split(', ').pop()}</div>
      </div>`;
    recentList.prepend(row);
  }

  // ------------------------------------------------------------- Core submit
  async function submitScan(code) {
    if (!code || !code.trim()) return;
    if (!navigator.onLine) {
      renderResult({ ok: false, is_warning: false, message: "You're offline — scan not recorded." });
      beep('error');
      return;
    }
    try {
      const resp = await fetch(SCAN_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
        body: JSON.stringify({ code: code.trim(), event_id: EVENT_ID, session_id: SESSION_ID, check_type: checkType }),
      });
      const data = await resp.json();
      renderResult(data);
      beep(data.ok ? 'success' : 'warning');

      if (data.ok && data.attendance) {
        prependRecentScan(data.attendance, data.person.full_name, data.person.person_id, data.attendance.check_type);
        const counter = data.attendance.check_type === 'Check-in' ? countedIn : countedOut;
        if (counter) counter.textContent = String((parseInt(counter.textContent, 10) || 0) + 1);
      }
    } catch (err) {
      renderResult({ ok: false, is_warning: false, message: 'Network error — could not reach the server.' });
      beep('error');
    }
  }

  // Manual entry
  const manualForm = document.getElementById('manual-scan-form');
  const manualInput = document.getElementById('manual-code');
  if (manualForm) {
    manualForm.addEventListener('submit', function (e) {
      e.preventDefault();
      submitScan(manualInput.value);
      manualInput.value = '';
      manualInput.focus();
    });
  }

  // ------------------------------------------------------------- Camera
  const startBtn = document.getElementById('start-camera-btn');
  const placeholder = document.getElementById('camera-placeholder');
  const reader = document.getElementById('qr-reader');
  const reticle = document.getElementById('scan-reticle');

  if (startBtn && window.Html5Qrcode) {
    startBtn.addEventListener('click', async function () {
      placeholder.style.display = 'none';
      reader.style.display = 'block';
      reticle.style.display = 'block';

      const qr = new Html5Qrcode('qr-reader');
      try {
        await qr.start(
          { facingMode: 'environment' },
          { fps: 10, qrbox: 220 },
          (decodedText) => {
            const now = Date.now();
            if (now - lastScanAt < SCAN_COOLDOWN_MS) return;
            lastScanAt = now;
            submitScan(decodedText);
          },
          () => { /* per-frame decode failures are normal, ignore */ }
        );
        scanning = true;
      } catch (err) {
        placeholder.style.display = 'flex';
        reader.style.display = 'none';
        reticle.style.display = 'none';
        placeholder.querySelector('div').textContent = 'Camera unavailable — use manual entry below, or check browser permissions.';
      }
    });
  } else if (startBtn) {
    startBtn.addEventListener('click', function () {
      placeholder.querySelector('div').textContent = 'Camera library failed to load — use manual entry below.';
    });
  }
})();
