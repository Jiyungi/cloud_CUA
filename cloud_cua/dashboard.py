from __future__ import annotations


def render_dashboard() -> str:
    return HTML


HTML = r"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Cloud CUA</title>
  <style>
    :root {
      --bg: #eef3f8;
      --surface: #ffffff;
      --surface-2: #f7fafc;
      --ink: #071326;
      --muted: #53657a;
      --border: #d8e1ec;
      --primary: #2457d6;
      --primary-dark: #173b96;
      --success: #12805c;
      --warning: #9a6516;
      --danger: #b42318;
      --info: #2b6cb0;
      --shadow: 0 18px 45px rgba(15, 23, 42, .08);
      --radius: 8px;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--bg);
    }
    button, input, select, textarea { font: inherit; }
    button {
      min-height: 42px;
      border: 1px solid var(--primary);
      border-radius: 7px;
      background: var(--primary);
      color: #fff;
      padding: 0 14px;
      font-weight: 650;
      cursor: pointer;
      transition: background .18s ease, border-color .18s ease, transform .18s ease;
    }
    button:hover { background: var(--primary-dark); border-color: var(--primary-dark); }
    button:active { transform: translateY(1px); }
    button:focus-visible, input:focus-visible, select:focus-visible, textarea:focus-visible {
      outline: 3px solid rgba(36, 87, 214, .25);
      outline-offset: 2px;
    }
    button.secondary { background: #fff; color: var(--primary); }
    button.secondary:hover { background: #eef4ff; }
    button.quiet { background: var(--surface-2); border-color: var(--border); color: var(--ink); }
    button.quiet:hover { background: #edf3f9; }
    button.danger { background: var(--danger); border-color: var(--danger); }
    button:disabled { opacity: .55; cursor: not-allowed; transform: none; }
    input, select, textarea {
      width: 100%;
      border: 1px solid var(--border);
      border-radius: 7px;
      padding: 10px 11px;
      background: #fff;
      color: var(--ink);
    }
    label { display: block; color: var(--muted); font-size: 12px; font-weight: 750; margin: 12px 0 6px; }
    .topbar {
      height: 64px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 28px;
      background: #101b2f;
      color: #fff;
    }
    .brand { display: flex; align-items: center; gap: 12px; font-weight: 780; }
    .brand-mark { width: 30px; height: 30px; border-radius: 8px; background: #3b82f6; display: grid; place-items: center; }
    .shell {
      max-width: 1320px;
      margin: 0 auto;
      padding: 24px;
      display: grid;
      grid-template-columns: minmax(0, 1fr) 390px;
      gap: 18px;
    }
    .stack { display: grid; gap: 16px; align-content: start; }
    .panel {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
    }
    .panel.pad { padding: 18px; }
    .mission { min-height: 236px; display: grid; grid-template-columns: minmax(0, 1fr) 240px; gap: 18px; }
    .mission-main { padding: 22px; display: flex; flex-direction: column; justify-content: space-between; gap: 18px; }
    .kicker { color: var(--muted); font-size: 12px; font-weight: 780; margin-bottom: 8px; }
    h1, h2, h3 { margin: 0; text-wrap: balance; }
    h1 { font-size: 31px; line-height: 1.12; letter-spacing: 0; }
    h2 { font-size: 20px; }
    h3 { font-size: 15px; }
    .summary { color: var(--muted); line-height: 1.45; margin-top: 8px; max-width: 68ch; }
    .mission-side {
      border-left: 1px solid var(--border);
      background: var(--surface-2);
      padding: 18px;
      display: grid;
      align-content: start;
      gap: 12px;
    }
    .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    .split { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
    .chip {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      border: 1px solid var(--border);
      background: #fff;
      border-radius: 999px;
      padding: 6px 10px;
      color: var(--ink);
      font-size: 12px;
      font-weight: 650;
    }
    .dot { width: 8px; height: 8px; border-radius: 999px; background: var(--muted); }
    .dot.running { background: var(--info); }
    .dot.good { background: var(--success); }
    .dot.warn { background: var(--warning); }
    .dot.bad { background: var(--danger); }
    .mode-control {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      border: 1px solid var(--border);
      border-radius: 8px;
      overflow: hidden;
    }
    .mode-control button {
      border: 0;
      border-right: 1px solid var(--border);
      border-radius: 0;
      background: #fff;
      color: var(--ink);
      min-height: 44px;
    }
    .mode-control button:last-child { border-right: 0; }
    .mode-control button.active { background: #101b2f; color: #fff; }
    .lanes { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
    .lane {
      min-height: 108px;
      padding: 13px;
      background: var(--surface-2);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      display: grid;
      gap: 6px;
      align-content: start;
    }
    .lane strong { font-size: 13px; }
    .lane span { color: var(--muted); font-size: 13px; line-height: 1.35; }
    .proof-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 14px; }
    .proof-item { padding: 14px; border: 1px solid var(--border); border-radius: var(--radius); background: var(--surface-2); }
    .proof-item strong { display: block; margin-bottom: 8px; }
    .proof-item span { color: var(--muted); }
    .approval-list { display: grid; gap: 10px; margin-top: 12px; }
    .approval {
      border: 1px solid #e1b96b;
      background: #fff8e8;
      border-radius: var(--radius);
      padding: 12px;
      display: grid;
      gap: 10px;
    }
    .approval.approved { border-color: #a7d7c5; background: #effaf5; }
    .approval.denied { border-color: #f3b8b3; background: #fff2f1; }
    .voice-strip {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 12px;
      align-items: end;
    }
    .voice-actions { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
    .recording { background: var(--danger) !important; border-color: var(--danger) !important; }
    .activity {
      height: calc(100vh - 112px);
      min-height: 560px;
      display: grid;
      grid-template-rows: auto 1fr auto;
      overflow: hidden;
    }
    .activity-head { padding: 18px 18px 12px; border-bottom: 1px solid var(--border); }
    .timeline { overflow: auto; padding: 8px 12px 16px; display: grid; align-content: start; gap: 8px; }
    .event {
      display: grid;
      grid-template-columns: 72px minmax(0, 1fr);
      gap: 10px;
      padding: 10px 8px;
      border-radius: 7px;
    }
    .event:hover { background: var(--surface-2); }
    .event-source { color: var(--muted); font-size: 12px; font-weight: 750; text-transform: capitalize; }
    .event-msg { font-size: 13px; line-height: 1.4; word-break: break-word; }
    .empty { color: var(--muted); border: 1px dashed var(--border); border-radius: var(--radius); padding: 16px; background: var(--surface-2); }
    .devtools { box-shadow: none; }
    .devtools summary { cursor: pointer; font-weight: 750; padding: 14px 16px; }
    .devtools-body { border-top: 1px solid var(--border); padding: 0 16px 16px; }
    .modal-backdrop {
      position: fixed;
      inset: 0;
      z-index: 40;
      backdrop-filter: blur(5px);
      background: rgba(7, 19, 38, .55);
      display: none;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }
    .modal {
      width: min(520px, 100%);
      background: #fff;
      border-radius: var(--radius);
      box-shadow: 0 30px 90px rgba(0, 0, 0, .3);
      padding: 24px;
    }
    .modal p { color: var(--muted); line-height: 1.5; }
    @media (max-width: 980px) {
      .shell { grid-template-columns: 1fr; padding: 14px; }
      .activity { height: auto; min-height: 360px; }
      .mission { grid-template-columns: 1fr; }
      .mission-side { border-left: 0; border-top: 1px solid var(--border); }
      .lanes, .proof-grid { grid-template-columns: 1fr; }
      .voice-strip { grid-template-columns: 1fr; align-items: stretch; }
      .voice-actions { justify-content: flex-start; }
      .split { align-items: stretch; flex-direction: column; }
      .mode-control { width: 100%; }
    }
    @media (prefers-reduced-motion: reduce) {
      * { transition: none !important; }
    }
  </style>
</head>
<body>
  <header class="topbar">
    <div class="brand"><span class="brand-mark">C</span><span>Cloud CUA</span></div>
    <span id="headerState" class="chip"><span class="dot"></span>Local dashboard</span>
  </header>

  <main class="shell">
    <div class="stack">
      <section class="panel mission">
        <div class="mission-main">
          <div>
            <div class="kicker">Deployment run</div>
            <h1 id="statusTitle">Waiting for Codex</h1>
            <p id="runSummary" class="summary">Start from Codex through MCP, or use this local repo to test the control loop.</p>
          </div>
          <div class="row">
            <button onclick="startRun()">Start local repo</button>
            <button class="secondary" onclick="openBrowser()">Open cloud login</button>
            <button class="quiet" onclick="runDeploy()">Deploy</button>
            <button class="quiet" onclick="pauseRun()">Pause</button>
            <button class="quiet" onclick="resumeRun()">Resume</button>
          </div>
        </div>
        <div class="mission-side">
          <div class="split"><strong>Run</strong><span id="runIdPill" class="chip">No run</span></div>
          <div><span class="kicker">Cloud</span><div id="cloudLabel">AWS</div></div>
          <div><span class="kicker">Target</span><div id="targetLabel">Not analyzed</div></div>
          <div><span class="kicker">Current step</span><div id="stepLabel">Idle</div></div>
        </div>
      </section>

      <section class="panel pad">
        <div class="split">
          <div>
            <h2>Mode</h2>
            <p class="summary">Switch how much the agent explains or asks before the next step.</p>
          </div>
          <div class="mode-control">
            <button id="mode-vibe" onclick="setMode('vibe')">Vibe</button>
            <button id="mode-teach" onclick="setMode('teach')">Teach</button>
            <button id="mode-expert" onclick="setMode('expert')">Expert</button>
          </div>
        </div>
      </section>

      <section class="panel pad">
        <div class="split">
          <div>
            <h2>Voice</h2>
            <p id="voiceState" class="summary">Checking Gradium voice availability.</p>
          </div>
          <span id="voiceKeyChip" class="chip">Voice unknown</span>
        </div>
        <div class="voice-strip">
          <div>
            <label for="voiceText">Command or question</label>
            <textarea id="voiceText" rows="2" placeholder="pause, switch to Teach mode, why this service?"></textarea>
          </div>
          <div class="voice-actions">
            <button id="micButton" class="secondary" onclick="toggleRecording()">Start mic</button>
            <button class="secondary" onclick="sendVoice()">Route text</button>
            <button class="quiet" onclick="speakLatest()">Speak latest</button>
          </div>
        </div>
      </section>

      <section class="panel pad">
        <h2>Control Loop</h2>
        <p class="summary">Each part has a different job. The dashboard should make it obvious who acted and what proof exists.</p>
        <div class="lanes">
          <div class="lane"><strong>Codex</strong><span id="codexLane">Plans from repo context.</span></div>
          <div class="lane"><strong>H CUA</strong><span id="hLane">Waits for login, then operates browser.</span></div>
          <div class="lane"><strong>User</strong><span id="userLane">Approves risky cloud actions.</span></div>
          <div class="lane"><strong>Verifier</strong><span id="verifierLane">Checks AWS/GCP directly.</span></div>
        </div>
      </section>

      <section class="panel pad">
        <div class="split">
          <h2>Approvals</h2>
          <button class="secondary" onclick="loadApprovals()">Refresh</button>
        </div>
        <div id="approvals" class="approval-list"><div class="empty">No approval requests yet.</div></div>
      </section>

      <section class="panel pad">
        <h2>Proof</h2>
        <div class="proof-grid">
          <div class="proof-item"><strong>Cloud identity</strong><span id="identityState">Not checked</span></div>
          <div class="proof-item"><strong>Resources</strong><span id="resourceState">Not checked</span></div>
          <div class="proof-item"><strong>Live app</strong><span id="liveState">No URL yet</span></div>
        </div>
        <div class="row" style="margin-top:14px">
          <button class="secondary" onclick="runVerifier()">Run verifier</button>
          <button class="secondary" onclick="awsCleanupDryRun()">AWS cleanup dry run</button>
          <button class="secondary" onclick="writeReport()">Write report</button>
        </div>
      </section>

      <details class="panel devtools">
        <summary>Developer tools</summary>
        <div class="devtools-body">
          <label for="repo">Repo path</label>
          <input id="repo" />
          <div class="row">
            <div style="min-width:160px; flex:1">
              <label for="cloud">Cloud</label>
              <select id="cloud"><option value="aws">AWS</option><option value="gcp">GCP</option></select>
            </div>
            <div style="min-width:180px; flex:1">
              <label for="awsTask">Deployment task override</label>
              <textarea id="awsTask" rows="2" placeholder="Deploy this repo safely on AWS under $5"></textarea>
            </div>
          </div>
          <div class="row" style="margin-top:12px">
            <button class="secondary" onclick="showLogin()">Show login gate</button>
            <button class="secondary" onclick="hInspect()">H inspect</button>
            <button class="secondary" onclick="runDeploy()">Deploy</button>
            <button class="secondary" onclick="runGcpTask()">Run GCP task</button>
            <button class="secondary" onclick="cleanupH()">Clean H sessions</button>
          </div>
        </div>
      </details>
    </div>

    <aside class="panel activity">
      <div class="activity-head">
        <div class="split"><h2>Activity</h2><span id="eventCount" class="chip">0 events</span></div>
        <p class="summary">Live timeline from Codex, H CUA, user approvals, and verifiers.</p>
      </div>
      <div id="events" class="timeline"><div class="empty">No events yet.</div></div>
      <div style="padding:12px 18px; border-top:1px solid var(--border)">
        <button class="secondary" onclick="refresh()">Refresh</button>
      </div>
    </aside>
  </main>

  <div id="loginModal" class="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="loginTitle">
    <div class="modal">
      <h2 id="loginTitle">Manual login required</h2>
      <p id="loginCopy">Log into AWS in this browser window. Click Continue when done.</p>
      <div class="row">
        <button onclick="continueLogin()">Continue</button>
        <button class="secondary" onclick="hideLogin()">Cancel</button>
      </div>
    </div>
  </div>

<script>
let currentRun = null;
let lastEvents = [];
let voiceReady = false;
let containerMode = false;
let mediaRecorder = null;
let audioChunks = [];
const continuedApprovals = new Set();
const repoInput = document.getElementById('repo');
initDefaults();

function body(extra = {}) { return { repo_path: repoInput.value, ...extra }; }
async function post(url, payload) {
  const r = await fetch(url, { method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify(payload) });
  if (!r.ok) throw new Error(await r.text());
  return await r.json();
}
async function startRun() {
  localStorage.setItem('cloud_cua_repo', repoInput.value);
  currentRun = await post('/runs', { repo_path: repoInput.value, cloud: cloud.value, mode: currentRun?.mode || 'vibe' });
  showLogin();
  await refresh();
}
async function refresh() {
  if (!currentRun) return;
  currentRun = await (await fetch(`/runs/${currentRun.run_id}?repo_path=${encodeURIComponent(repoInput.value)}`)).json();
  const ev = await (await fetch(`/runs/${currentRun.run_id}/events?repo_path=${encodeURIComponent(repoInput.value)}&limit=100`)).json();
  lastEvents = ev;
  renderRun();
  renderEvents(ev);
  renderProof(ev);
  await loadApprovals();
  await loadCapabilities();
}
function renderRun() {
  statusTitle.textContent = titleForStatus(currentRun.status);
  headerState.innerHTML = `<span class="dot ${dotClass(currentRun.status)}"></span>${currentRun.status}`;
  runIdPill.textContent = currentRun.run_id || 'No run';
  cloudLabel.textContent = currentRun.cloud?.toUpperCase() || 'AWS';
  targetLabel.textContent = currentRun.target || 'Not analyzed';
  stepLabel.textContent = currentRun.current_step || 'Idle';
  runSummary.innerHTML = `Repo: <b>${shortPath(repoInput.value)}</b><br>Mode: <b>${currentRun.mode}</b>`;
  for (const m of ['vibe', 'teach', 'expert']) document.getElementById('mode-' + m).classList.toggle('active', currentRun.mode === m);
}
function renderEvents(ev) {
  eventCount.textContent = `${ev.length} events`;
  if (!ev.length) { events.innerHTML = '<div class="empty">No events yet.</div>'; return; }
  events.innerHTML = ev.slice().reverse().map(e => `
    <div class="event">
      <div class="event-source">${escapeHtml(e.source)}</div>
      <div class="event-msg"><strong>${escapeHtml(e.type)}</strong><br>${escapeHtml(e.message)}</div>
    </div>
  `).join('');
  codexLane.textContent = latest('codex') || 'Plans from repo context.';
  hLane.textContent = latest('h_cua') || (containerMode ? 'Docker mode can supervise and verify. Run host-local Python for real H browser takeover.' : 'Waits for login, then operates browser.');
  userLane.textContent = latest('user') || 'Approves risky cloud actions.';
  verifierLane.textContent = latest('verifier') || 'Checks AWS/GCP directly.';
}
async function loadApprovals() {
  if (!currentRun) return;
  const items = await (await fetch(`/runs/${currentRun.run_id}/approvals?repo_path=${encodeURIComponent(repoInput.value)}`)).json();
  if (!items.length) { approvals.innerHTML = '<div class="empty">No approval requests yet.</div>'; return; }
  approvals.innerHTML = items.map(a => `
    <div class="approval ${escapeHtml(a.status)}">
      <div class="split"><strong>${escapeHtml(a.action)}</strong><span class="chip">${escapeHtml(a.risk_level)} / ${escapeHtml(a.status)}</span></div>
      <div class="summary">${escapeHtml(a.reason)}</div>
      ${a.status === 'pending' ? `<div class="row"><button onclick="decideApproval('${a.approval_id}', true)">Approve</button><button class="secondary" onclick="decideApproval('${a.approval_id}', false)">Deny</button></div>` : ''}
    </div>
  `).join('');
  maybeContinueApprovedApproval(items);
}
async function decideApproval(id, approved) {
  const approval = await post(`/runs/${currentRun.run_id}/approval-decision`, body({approval_id: id, approved}));
  await refresh();
  if (approved) continueAfterApproval(approval);
}
async function setMode(m) { if (!currentRun) return; await post(`/runs/${currentRun.run_id}/mode`, body({mode:m})); await refresh(); }
async function openBrowser() { if (!currentRun) return; await post(`/runs/${currentRun.run_id}/open-browser`, body()); showLogin(); await refresh(); }
function showLogin() {
  loginCopy.textContent = cloud.value === 'gcp' ? 'Log into GCP in this browser window. Click Continue when done.' : 'Log into AWS in this browser window. Click Continue when done.';
  loginModal.style.display = 'flex';
}
function hideLogin() { loginModal.style.display = 'none'; }
async function continueLogin() { if (!currentRun) return; await post(`/runs/${currentRun.run_id}/continue-login`, body()); hideLogin(); await refresh(); }
async function pauseRun() { if (!currentRun) return; await post(`/runs/${currentRun.run_id}/pause`, body()); await refresh(); }
async function resumeRun() { if (!currentRun) return; await post(`/runs/${currentRun.run_id}/resume`, body()); await refresh(); }
async function hInspect() { if (!currentRun) return; await post(`/runs/${currentRun.run_id}/h-inspect`, body()); await refresh(); }
async function runAwsTask() {
  if (!currentRun) return;
  await post(`/runs/${currentRun.run_id}/aws-deploy`, body({task: awsTask.value || null, max_spend_usd: 5}));
  await refresh();
}
async function runDeploy() {
  if (!currentRun) return;
  if ((cloud.value || currentRun.cloud) === 'gcp') {
    await runGcpTask();
  } else {
    await runAwsTask();
  }
}
async function runGcpTask() {
  if (!currentRun) return;
  await post(`/runs/${currentRun.run_id}/gcp-deploy`, body({task: awsTask.value || null}));
  await refresh();
}
async function runVerifier() { if (!currentRun) return; await post(`/runs/${currentRun.run_id}/verify`, body()); await refresh(); }
async function writeReport() { if (!currentRun) return; await post(`/runs/${currentRun.run_id}/report`, body()); await refresh(); }
async function sendVoice() { if (!currentRun || !voiceText.value.trim()) return; await post(`/runs/${currentRun.run_id}/voice`, body({text: voiceText.value})); voiceText.value = ''; await refresh(); }
async function cleanupH() { await post('/h-cleanup', body()); await refresh(); }
function continueAfterApproval(approval) {
  if (!approval?.approval_id || continuedApprovals.has(approval.approval_id)) return;
  continuedApprovals.add(approval.approval_id);
  const action = String(approval?.action || '');
  if (
    action.startsWith('Run AWS deployment task:') ||
    action === 'Run GCP Cloud Run deployment task'
  ) {
    post(`/runs/${currentRun.run_id}/resume-approved`, body()).then(refresh).catch(console.error);
  }
}
function maybeContinueApprovedApproval(items) {
  if (!currentRun || !['approval_required', 'approval_approved'].includes(currentRun.current_step)) return;
  const approval = items.find(a => a.status === 'approved' && (
    String(a.action || '').startsWith('Run AWS deployment task:') ||
    a.action === 'Run GCP Cloud Run deployment task'
  ));
  if (approval) continueAfterApproval(approval);
}
async function awsCleanupDryRun() {
  const runId = currentRun ? currentRun.run_id : null;
  await post('/aws-cleanup', body({run_id: runId, dry_run: true}));
  await refresh();
}
async function loadCapabilities() {
  if (!repoInput.value) return;
  try {
    const caps = await (await fetch(`/capabilities?repo_path=${encodeURIComponent(repoInput.value)}`)).json();
    voiceReady = Boolean(caps.gradium_api_key_present);
    containerMode = Boolean(caps.container_mode);
    micButton.disabled = !voiceReady || !currentRun;
    voiceKeyChip.textContent = voiceReady ? 'Gradium ready' : 'Voice disabled';
    voiceState.textContent = voiceReady ? 'Mic commands use Gradium STT, then the same router as typed commands.' : 'Add GRADIUM_API_KEY to enable microphone and speech playback. Typed commands still work.';
    if (containerMode) hLane.textContent = 'Docker mode can supervise and verify. Run host-local Python for real H browser takeover.';
  } catch {
    voiceReady = false;
    micButton.disabled = true;
    voiceKeyChip.textContent = 'Voice unavailable';
  }
}
async function toggleRecording() {
  if (!currentRun || !voiceReady) return;
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop();
    return;
  }
  const stream = await navigator.mediaDevices.getUserMedia({audio: true});
  const mime = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : '';
  mediaRecorder = new MediaRecorder(stream, mime ? {mimeType: mime} : undefined);
  audioChunks = [];
  mediaRecorder.ondataavailable = e => { if (e.data.size > 0) audioChunks.push(e.data); };
  mediaRecorder.onstop = async () => {
    stream.getTracks().forEach(track => track.stop());
    micButton.textContent = 'Start mic';
    micButton.classList.remove('recording');
    const blob = new Blob(audioChunks, {type: mediaRecorder.mimeType || 'audio/webm'});
    const base64 = await blobToBase64(blob);
    const inputFormat = blob.type.includes('wav') ? 'wav' : 'webm';
    await post(`/runs/${currentRun.run_id}/voice-transcribe`, body({audio_base64: base64, input_format: inputFormat}));
    await refresh();
  };
  mediaRecorder.start();
  micButton.textContent = 'Stop mic';
  micButton.classList.add('recording');
}
async function speakLatest() {
  if (!currentRun || !voiceReady) return;
  const latestText = latest('h_cua') || latest('verifier') || latest('system') || 'No Cloud CUA update is available yet.';
  const result = await post(`/runs/${currentRun.run_id}/speak`, body({text: latestText.slice(0, 500)}));
  if (result.audio_base64) {
    const audio = new Audio(`data:audio/wav;base64,${result.audio_base64}`);
    await audio.play();
  }
  await refresh();
}
function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}
function latest(source) {
  const event = lastEvents.slice().reverse().find(e => e.source === source);
  return event ? event.message : '';
}
function renderProof(ev) {
  const evidence = JSON.stringify(ev.filter(e => e.source === 'verifier').map(e => e.evidence || {}));
  identityState.textContent = evidence.includes('aws_identity') || evidence.includes('gcp_auth_list') ? 'Checked' : 'Not checked';
  resourceState.textContent = evidence.includes('aws_tagged_run_resources') || evidence.includes('gcp_cloud_run_services') || evidence.includes('aws_amplify_list_apps') ? 'Checked' : 'Not checked';
  liveState.textContent = evidence.includes('http_live_url') || evidence.includes('playwright_render') ? 'Checked' : 'No URL yet';
}
function titleForStatus(status) {
  return ({created:'Preparing run', waiting_for_login:'Waiting for cloud login', running:'Deployment running', paused:'Paused', verifying:'Verifying deployment', completed:'Deployment complete', blocked:'Needs attention', failed:'Failed'}[status] || 'Deployment status');
}
function dotClass(status) {
  if (status === 'completed') return 'good';
  if (status === 'running' || status === 'verifying') return 'running';
  if (status === 'blocked' || status === 'waiting_for_login' || status === 'paused') return 'warn';
  if (status === 'failed') return 'bad';
  return '';
}
function shortPath(p) { return p ? p.split(/[\\/]/).slice(-2).join('/') : 'No repo selected'; }
function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
}
async function initDefaults() {
  const saved = localStorage.getItem('cloud_cua_repo');
  if (saved) { repoInput.value = saved; await loadCapabilities(); return; }
  try { repoInput.value = (await (await fetch('/defaults')).json()).repo_path || ''; } catch {}
  await loadCapabilities();
}
repoInput.addEventListener('change', loadCapabilities);
setInterval(refresh, 3500);
</script>
</body>
</html>
"""
