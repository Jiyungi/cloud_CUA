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
    .skill-grid { display: grid; grid-template-columns: 1.1fr .9fr; gap: 18px; margin-top: 14px; }
    .skill-meta { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
    .skill-meta > div { border-left: 3px solid var(--border); padding-left: 10px; min-width: 0; }
    .skill-meta strong { display: block; font-size: 12px; color: var(--muted); margin-bottom: 5px; }
    .skill-meta span { display: block; overflow-wrap: anywhere; }
    .compact-list { margin: 8px 0 0; padding-left: 18px; color: var(--muted); font-size: 13px; line-height: 1.45; }
    .lesson { border-left: 4px solid var(--warning); background: #fff8e8; padding: 12px; margin-top: 14px; }
    .lesson[hidden] { display: none; }
    .proof-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin-top: 14px; }
    .safety-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-top: 14px; }
    .safety-item { border: 1px solid var(--border); background: var(--surface-2); border-radius: var(--radius); padding: 13px; min-height: 92px; }
    .safety-item strong { display:block; margin-bottom:7px; }
    .safety-item span { color: var(--muted); font-size:13px; line-height:1.4; display:block; }
    .progress-track { height: 7px; background: #dbe3ef; border-radius: 999px; overflow:hidden; margin-top:10px; }
    .progress-bar { height:100%; width:0; background:var(--primary); transition:width .2s ease; }
    .progress-bar.warn { background:var(--warning); }
    .progress-bar.bad { background:var(--danger); }
    .secret-row { border-top:1px solid var(--border); padding-top:12px; margin-top:12px; }
    .secret-row:first-child { border-top:0; padding-top:0; margin-top:0; }
    .secret-choice { display:flex; gap:14px; margin:8px 0; color:var(--muted); font-size:13px; }
    .secret-choice label { display:flex; gap:6px; align-items:center; margin:0; }
    .secret-choice input { width:auto; }
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
      max-height: calc(100vh - 40px);
      overflow: auto;
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
      .lanes, .proof-grid, .safety-grid { grid-template-columns: 1fr; }
      .skill-grid, .skill-meta { grid-template-columns: 1fr; }
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
            <button class="secondary" onclick="openBrowser()">Open cloud login</button>
            <button class="quiet" onclick="runDeploy()">Deploy</button>
            <button class="quiet" onclick="pauseRun()">Pause</button>
            <button class="quiet" onclick="resumeRun()">Resume</button>
            <button class="quiet" onclick="cancelRun()">Cancel</button>
          </div>
        </div>
        <div class="mission-side">
          <div class="split"><strong>Run</strong><span id="runIdPill" class="chip">No run</span></div>
          <div><span class="kicker">Cloud</span><div id="cloudLabel">AWS</div></div>
          <div><span class="kicker">Target</span><div id="targetLabel">Not analyzed</div></div>
          <div><span class="kicker">Current step</span><div id="stepLabel">Idle</div></div>
          <div><span class="kicker">H session</span><div id="hJobLabel">Idle</div></div>
        </div>
      </section>

      <section class="panel pad">
        <div class="split">
          <div><h2>Safety</h2><p class="summary">Identity, runtime configuration, and cost must be proven before creation.</p></div>
          <span id="safetyChip" class="chip">Checking</span>
        </div>
        <div class="safety-grid">
          <div class="safety-item"><strong>AWS account</strong><span id="accountMatchState">Not checked</span></div>
          <div class="safety-item"><strong>Runtime configuration</strong><span id="runtimeConfigState">Not checked</span></div>
          <div class="safety-item"><strong>Cost policy</strong><span id="costState">Not estimated</span><div class="progress-track"><div id="costBar" class="progress-bar"></div></div></div>
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
          <div>
            <h2>Skills</h2>
            <p class="summary">The active deployment recipe H can load for this run.</p>
          </div>
          <button id="syncSkillsButton" class="secondary" onclick="syncSkills()">Sync H skills</button>
        </div>
        <div class="skill-grid">
          <div>
            <div class="skill-meta">
              <div><strong>Active skill</strong><span id="activeSkill">Not selected</span></div>
              <div><strong>H catalog</strong><span id="skillSync">Not synced</span></div>
              <div><strong>Autonomy</strong><span id="skillAutonomy">Not assigned</span></div>
            </div>
            <div id="lessonPanel" class="lesson" hidden>
              <strong>Lesson awaiting review</strong>
              <p id="lessonFailure" class="summary"></p>
              <p id="lessonRule" class="summary"></p>
            </div>
          </div>
          <div>
            <strong>Contract facts</strong>
            <ul id="skillFacts" class="compact-list"><li>No contract yet.</li></ul>
            <strong style="display:block; margin-top:12px">Verifier gates</strong>
            <ul id="skillGates" class="compact-list"><li>No gates selected.</li></ul>
          </div>
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
          <div class="proof-item"><strong>Live app</strong><span id="liveState">No URL yet</span><a id="liveLink" target="_blank" rel="noreferrer" hidden>Open app</a></div>
          <div class="proof-item"><strong>Report</strong><span id="reportState">Not written</span></div>
          <div class="proof-item"><strong>Cleanup</strong><span id="cleanupState">Not run</span></div>
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
            <button class="secondary" onclick="startRun()">Start local repo</button>
            <button class="secondary" onclick="showLogin()">Show login gate</button>
            <button class="secondary" onclick="hInspect()">H inspect</button>
            <button class="secondary" onclick="runDeploy()">Deploy</button>
            <button class="secondary" onclick="runGcpTask()">Run GCP task</button>
            <button class="secondary" onclick="cleanupH()">Clean H sessions</button>
          </div>
          <label for="runPicker">Recent runs for this repo</label>
          <select id="runPicker" onchange="selectRun(this.value)"><option value="">No runs loaded</option></select>
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
        <button class="secondary" onclick="cancelRun()">Cancel run</button>
      </div>
    </div>
  </div>

  <div id="runtimeModal" class="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="runtimeTitle">
    <div class="modal">
      <h2 id="runtimeTitle">Runtime configuration required</h2>
      <p>Cloud CUA stores new secret values directly in AWS Systems Manager Parameter Store. Plaintext is not saved in this app, the repo, the run, or the H session.</p>
      <div id="publicConfigWarning" class="lesson" hidden></div>
      <div id="runtimeFields"></div>
      <div class="row" style="margin-top:18px">
        <button onclick="saveRuntimeConfiguration()">Store in AWS and continue</button>
        <button class="secondary" onclick="cancelRun()">Cancel run</button>
      </div>
      <p id="runtimeError" class="summary"></p>
    </div>
  </div>

  <div id="costModal" class="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="costTitle">
    <div class="modal">
      <h2 id="costTitle">Cost action required</h2>
      <p id="costModalCopy">The run reached its estimated spending policy cap. Cloud CUA will not perform more paid actions until tagged resources are cleaned up or you approve a higher cap.</p>
      <p><strong>AWS billing data is delayed.</strong> This is a live-price estimate and policy guard, not a bank-level spending guarantee.</p>
      <div id="cleanupPreview" class="empty">Run a cleanup preview before deleting anything.</div>
      <div class="row" style="margin-top:18px">
        <button id="cleanupGateButton" class="danger" onclick="costCleanupAction()">Review tagged cleanup</button>
        <button class="secondary" onclick="requestCostExtension()">Request $5 extension</button>
      </div>
      <p id="costGateError" class="summary"></p>
    </div>
  </div>

<script>
let currentRun = null;
let lastEvents = [];
let voiceReady = false;
let voiceMuted = false;
let containerMode = false;
let mediaRecorder = null;
let audioChunks = [];
let runtimeStatus = null;
let costStatus = null;
let cleanupReviewed = false;
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
  const runResponse = await fetch(`/runs/${currentRun.run_id}?repo_path=${encodeURIComponent(repoInput.value)}`);
  if (!runResponse.ok) { statusTitle.textContent = 'Run connection lost'; return; }
  currentRun = await runResponse.json();
  const ev = await (await fetch(`/runs/${currentRun.run_id}/events?repo_path=${encodeURIComponent(repoInput.value)}&limit=100`)).json();
  lastEvents = ev;
  renderRun();
  renderEvents(ev);
  renderProof(ev);
  await loadApprovals();
  await loadCapabilities();
  await loadSkillState();
  await loadSafetyState();
  await loadRunPicker();
}
function renderRun() {
  statusTitle.textContent = titleForStatus(currentRun.status);
  headerState.innerHTML = `<span class="dot ${dotClass(currentRun.status)}"></span>${currentRun.status}`;
  runIdPill.textContent = currentRun.run_id || 'No run';
  cloudLabel.textContent = currentRun.cloud?.toUpperCase() || 'AWS';
  targetLabel.textContent = currentRun.target || 'Not analyzed';
  stepLabel.textContent = currentRun.current_step || 'Idle';
  const hJob = currentRun.h_job;
  hJobLabel.textContent = hJob ? `${readableStatus(hJob.status)} / ${readableStatus(hJob.milestone)}` : 'Idle';
  runSummary.innerHTML = `Repo: <b>${shortPath(repoInput.value)}</b><br>Mode: <b>${currentRun.mode}</b>`;
  const finalUrl = currentRun.live_urls?.[0];
  liveLink.hidden = !finalUrl;
  if (finalUrl) { liveLink.href = finalUrl; liveLink.textContent = 'Open app'; }
  reportState.textContent = currentRun.report_path ? shortPath(currentRun.report_path) : 'Not written';
  cleanupState.textContent = readableStatus(currentRun.cleanup_state?.status || 'not_run');
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
}
async function decideApproval(id, approved) {
  await post(`/runs/${currentRun.run_id}/approval-decision`, body({approval_id: id, approved}));
  await refresh();
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
async function cancelRun() {
  if (!currentRun) return;
  await post(`/runs/${currentRun.run_id}/cancel`, body());
  hideLogin();
  runtimeModal.style.display = 'none';
  costModal.style.display = 'none';
  await refresh();
}
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
async function sendVoice() {
  if (!currentRun || !voiceText.value.trim()) return;
  const result = await post(`/runs/${currentRun.run_id}/voice`, body({text: voiceText.value}));
  voiceText.value = '';
  voiceState.textContent = result.response || 'Command routed.';
  if (result.ui_action === 'open_logs') document.querySelector('.activity').scrollIntoView({behavior:'smooth'});
  if (result.ui_action === 'mute_voice') voiceMuted = true;
  await refresh();
}
async function cleanupH() { await post('/h-cleanup', body()); await refresh(); }
async function awsCleanupDryRun() {
  const runId = currentRun ? currentRun.run_id : null;
  await post('/aws-cleanup', body({run_id: runId, dry_run: true}));
  await refresh();
}
async function loadSafetyState() {
  if (!currentRun) return;
  const query = `repo_path=${encodeURIComponent(repoInput.value)}`;
  try {
    const [identityResponse, runtimeResponse, costResponse] = await Promise.all([
      fetch(`/runs/${currentRun.run_id}/browser-identity?${query}`),
      fetch(`/runs/${currentRun.run_id}/runtime-configuration?${query}`),
      fetch(`/runs/${currentRun.run_id}/cost?${query}`),
    ]);
    const identity = await identityResponse.json();
    runtimeStatus = await runtimeResponse.json();
    costStatus = await costResponse.json();
    accountMatchState.textContent = identity.status === 'matched'
      ? `Matched ${identity.expected_account_id}`
      : identity.status === 'mismatched'
        ? `Mismatch: browser ${identity.browser_account_id}, CLI ${identity.expected_account_id}`
        : readableStatus(identity.status || 'not_checked');
    runtimeConfigState.textContent = runtimeStatus.status === 'ready'
      ? `${runtimeStatus.references?.length || 0} secure reference(s) ready`
      : runtimeStatus.missing_names?.length
        ? `${runtimeStatus.missing_names.length} value(s) required`
        : readableStatus(runtimeStatus.status || 'not_checked');
    if (costStatus.status === 'not_configured') {
      costState.textContent = 'Created when a target is selected';
      costBar.style.width = '0%';
    } else {
      const used = Math.max(0, Number(costStatus.percent_used || 0));
      costState.textContent = `$${Number(costStatus.estimated_accrued_usd || 0).toFixed(3)} of $${Number(costStatus.max_spend_usd || 0).toFixed(2)} estimated`;
      costBar.style.width = `${Math.min(100, used)}%`;
      costBar.classList.toggle('warn', used >= 50 && used < 100);
      costBar.classList.toggle('bad', used >= 100);
    }
    const safe = identity.status === 'matched' && runtimeStatus.status === 'ready' && costStatus.status !== 'blocked';
    safetyChip.textContent = safe ? 'Ready' : 'Action required';
    if (currentRun.status === 'waiting_for_configuration' && runtimeStatus.status === 'required') showRuntimeModal(runtimeStatus);
    else runtimeModal.style.display = 'none';
    costModal.style.display = currentRun.status === 'cost_action_required' ? 'flex' : 'none';
  } catch (error) {
    safetyChip.textContent = 'Status unavailable';
  }
}
function showRuntimeModal(status) {
  runtimeStatus = status;
  const publicNames = status.public_build_names || [];
  publicConfigWarning.hidden = !publicNames.length;
  publicConfigWarning.innerHTML = publicNames.length
    ? `<strong>Public build configuration</strong><p class="summary">${publicNames.map(escapeHtml).join(', ')} will be visible in browser code and cannot contain secrets. Set these in the repo's normal local build environment before deployment.</p>`
    : '';
  runtimeFields.innerHTML = (status.missing_names || []).map((name, index) => `
    <div class="secret-row" data-secret-name="${escapeHtml(name)}">
      <strong>${escapeHtml(name)}</strong>
      <div class="secret-choice">
        <label><input type="radio" name="secret-source-${index}" value="value" checked onchange="toggleSecretSource(this)"> New secret</label>
        <label><input type="radio" name="secret-source-${index}" value="reference" onchange="toggleSecretSource(this)"> Existing SSM parameter</label>
      </div>
      <input class="source-value" type="password" autocomplete="new-password" placeholder="Stored directly in AWS SSM" aria-label="New value for ${escapeHtml(name)}">
      <input class="source-reference" hidden placeholder="/path/name or SSM parameter ARN" aria-label="Existing SSM reference for ${escapeHtml(name)}">
    </div>
  `).join('');
  runtimeError.textContent = '';
  runtimeModal.style.display = 'flex';
}
function toggleSecretSource(input) {
  const row = input.closest('.secret-row');
  const useReference = input.value === 'reference';
  row.querySelector('.source-value').hidden = useReference;
  row.querySelector('.source-reference').hidden = !useReference;
}
async function saveRuntimeConfiguration() {
  const values = {};
  const existing_references = {};
  for (const row of runtimeFields.querySelectorAll('.secret-row')) {
    const name = row.dataset.secretName;
    const source = row.querySelector('input[type=radio]:checked').value;
    const value = row.querySelector(source === 'reference' ? '.source-reference' : '.source-value').value.trim();
    if (!value) { runtimeError.textContent = `${name} is required.`; return; }
    (source === 'reference' ? existing_references : values)[name] = value;
  }
  runtimeError.textContent = 'Storing secure values in AWS SSM...';
  try {
    await post(`/runs/${currentRun.run_id}/runtime-configuration`, body({values, existing_references, region:'us-east-1'}));
    runtimeFields.innerHTML = '';
    runtimeModal.style.display = 'none';
    await refresh();
  } catch (error) {
    runtimeError.textContent = String(error);
  }
}
async function costCleanupAction() {
  costGateError.textContent = '';
  try {
    const result = await post('/aws-cleanup', body({run_id: currentRun.run_id, dry_run: !cleanupReviewed}));
    if (!cleanupReviewed) {
      cleanupReviewed = true;
      const items = result.actions || [];
      cleanupPreview.innerHTML = items.length
        ? `<strong>${items.length} tagged action(s) found</strong><ul class="compact-list">${items.map(item => `<li>${escapeHtml(item.service)}: ${escapeHtml(item.resource)}</li>`).join('')}</ul>`
        : 'No tagged resources belonging to this run were found.';
      cleanupGateButton.textContent = items.length ? 'Delete listed resources' : 'Refresh cleanup preview';
      cleanupGateButton.disabled = !items.length;
    } else {
      cleanupPreview.textContent = result.summary || 'Cleanup finished.';
      cleanupGateButton.disabled = true;
      await refresh();
    }
  } catch (error) { costGateError.textContent = String(error); }
}
async function requestCostExtension() {
  const currentCap = Number(costStatus?.max_spend_usd || 5);
  try {
    const result = await post(`/runs/${currentRun.run_id}/cost-extension`, body({new_cap_usd: currentCap + 5}));
    costGateError.textContent = result.approval_id ? 'Approve the cost extension in the Approvals panel.' : 'Cost policy extended.';
    await refresh();
  } catch (error) { costGateError.textContent = String(error); }
}
async function loadRunPicker() {
  if (!repoInput.value) return;
  try {
    const runs = await (await fetch(`/runs?repo_path=${encodeURIComponent(repoInput.value)}`)).json();
    runPicker.innerHTML = runs.length
      ? runs.slice().reverse().map(run => `<option value="${escapeHtml(run.run_id)}" ${run.run_id === currentRun?.run_id ? 'selected' : ''}>${escapeHtml(run.run_id)} / ${escapeHtml(readableStatus(run.status))}</option>`).join('')
      : '<option value="">No runs found</option>';
  } catch { runPicker.innerHTML = '<option value="">Runs unavailable</option>'; }
}
async function selectRun(runId) {
  if (!runId) return;
  const response = await fetch(`/runs/${encodeURIComponent(runId)}?repo_path=${encodeURIComponent(repoInput.value)}`);
  if (!response.ok) return;
  currentRun = await response.json();
  cleanupReviewed = false;
  const params = new URLSearchParams({repo_path:repoInput.value, run_id:runId});
  history.replaceState({}, '', `/?${params}`);
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
async function loadSkillState() {
  if (!currentRun) return;
  try {
    const state = await (await fetch(`/runs/${currentRun.run_id}/skill-state?repo_path=${encodeURIComponent(repoInput.value)}`)).json();
    const skill = state.active_skill;
    activeSkill.textContent = skill?.name || 'Not selected';
    skillSync.textContent = readableStatus(state.h_sync_status || 'not_synced');
    skillAutonomy.textContent = skill ? `Level ${skill.autonomy_level} of 5` : 'Not assigned';
    const present = state.present_facts || [];
    const missing = state.missing_facts || [];
    skillFacts.innerHTML = [
      ...present.map(item => `<li>${escapeHtml(item)} <strong style="color:var(--success)">ready</strong></li>`),
      ...missing.map(item => `<li>${escapeHtml(item)} <strong style="color:var(--danger)">missing</strong></li>`),
    ].join('') || '<li>No contract yet.</li>';
    skillGates.innerHTML = (state.verifier_gates || []).map(item => `<li>${escapeHtml(item)}</li>`).join('') || '<li>No gates selected.</li>';
    const lesson = state.lesson_candidate;
    lessonPanel.hidden = !lesson;
    if (lesson) {
      lessonFailure.textContent = lesson.failure;
      lessonRule.textContent = `Proposed rule: ${lesson.proposed_rule}`;
    }
  } catch {
    skillSync.textContent = 'Status unavailable';
  }
}
async function syncSkills() {
  syncSkillsButton.disabled = true;
  skillSync.textContent = 'Syncing';
  try {
    const result = await post('/skills/sync', body({dry_run:false}));
    skillSync.textContent = result.status === 'passed' ? 'Synced' : 'Blocked';
  } catch {
    skillSync.textContent = 'Sync failed';
  } finally {
    syncSkillsButton.disabled = false;
    await loadSkillState();
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
  if (!currentRun || !voiceReady || voiceMuted) return;
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
  identityState.textContent = hasPassedVerifier(ev, ['aws_identity', 'gcp_auth_list']) ? 'Checked' : 'Not checked';
  resourceState.textContent = hasPassedVerifier(ev, ['aws_tagged_run_resources', 'aws_ecs_run_services', 'gcp_cloud_run_services', 'aws_amplify_list_apps']) ? 'Checked' : 'Not checked';
  liveState.textContent = hasPassedVerifier(ev, ['http_live_url', 'playwright_render']) ? 'Checked' : 'No URL yet';
  if (hasFailedVerifier(ev, ['public_app_url', 'http_live_url', 'playwright_render', 'aws_ecs_run_services'])) liveState.textContent = 'Failed';
}
function verifierResults(ev) {
  return ev
    .filter(e => e.source === 'verifier')
    .flatMap(e => Array.isArray(e.evidence?.results) ? e.evidence.results : (e.evidence?.result ? [e.evidence.result] : []));
}
function hasPassedVerifier(ev, names) {
  return verifierResults(ev).some(result => names.includes(result.name) && result.status === 'passed');
}
function hasFailedVerifier(ev, names) {
  return verifierResults(ev).some(result => names.includes(result.name) && result.status === 'failed');
}
function titleForStatus(status) {
  return ({created:'Preparing run', waiting_for_login:'Waiting for cloud login', waiting_for_configuration:'Runtime configuration required', running:'Deployment running', paused:'Paused', verifying:'Verifying deployment', completed:'Deployment complete', blocked:'Needs attention', cost_action_required:'Cost action required', cancelled:'Run cancelled', failed:'Failed'}[status] || 'Deployment status');
}
function dotClass(status) {
  if (status === 'completed') return 'good';
  if (status === 'running' || status === 'verifying') return 'running';
  if (status === 'blocked' || status === 'waiting_for_login' || status === 'waiting_for_configuration' || status === 'paused') return 'warn';
  if (status === 'failed' || status === 'cost_action_required' || status === 'cancelled') return 'bad';
  return '';
}
function shortPath(p) { return p ? p.split(/[\\/]/).slice(-2).join('/') : 'No repo selected'; }
function readableStatus(value) { return String(value || '').replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase()); }
function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
}
async function initDefaults() {
  const params = new URLSearchParams(window.location.search);
  const linkedRepo = params.get('repo_path');
  const linkedRun = params.get('run_id');
  if (linkedRepo && linkedRun) {
    repoInput.value = linkedRepo;
    localStorage.setItem('cloud_cua_repo', linkedRepo);
    try {
      const response = await fetch(`/runs/${encodeURIComponent(linkedRun)}?repo_path=${encodeURIComponent(linkedRepo)}`);
      if (!response.ok) throw new Error(await response.text());
      currentRun = await response.json();
      cloud.value = currentRun.cloud || 'aws';
      await loadCapabilities();
      await refresh();
      if (currentRun.status === 'waiting_for_login') showLogin();
      return;
    } catch (error) {
      statusTitle.textContent = 'Run could not be loaded';
      runSummary.textContent = String(error);
    }
  }
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
