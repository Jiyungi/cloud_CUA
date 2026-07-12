from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .dashboard import render_dashboard
from .orchestrator import Orchestrator


class StartRequest(BaseModel):
    repo_path: str
    cloud: str = "aws"
    mode: str = "vibe"


class ModeRequest(BaseModel):
    repo_path: str
    mode: str


class RepoRunRequest(BaseModel):
    repo_path: str


class VoiceRequest(BaseModel):
    repo_path: str
    text: str


class HTaskRequest(BaseModel):
    repo_path: str
    task: str | None = None


class AWSDeploymentTaskRequest(BaseModel):
    repo_path: str
    task: str | None = None
    target: str | None = None
    max_spend_usd: float = 5.0


class VerifierRequest(BaseModel):
    repo_path: str
    verifier_name: str = "default"
    url: str | None = None


class ApprovalRequest(BaseModel):
    repo_path: str
    action: str
    reason: str
    risk_level: str = "medium"


class ApprovalDecisionRequest(BaseModel):
    repo_path: str
    approval_id: str
    approved: bool


def create_app() -> FastAPI:
    app = FastAPI(title="Cloud CUA")

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/defaults")
    def defaults():
        return {"repo_path": str(Path.cwd())}

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return render_dashboard()

    @app.post("/runs")
    def start_run(req: StartRequest):
        return Orchestrator(req.repo_path).start_deployment(req.cloud, req.mode)

    @app.get("/runs")
    def list_runs(repo_path: str):
        return Orchestrator(repo_path).list_runs()

    @app.get("/runs/{run_id}")
    def get_run(run_id: str, repo_path: str):
        return Orchestrator(repo_path).get_status(run_id)

    @app.get("/runs/{run_id}/events")
    def get_events(run_id: str, repo_path: str, limit: int = 100):
        return Orchestrator(repo_path).get_events(run_id, limit)

    @app.post("/runs/{run_id}/mode")
    def set_mode(run_id: str, req: ModeRequest):
        return Orchestrator(req.repo_path).set_mode(run_id, req.mode)

    @app.post("/runs/{run_id}/open-browser")
    def open_browser(run_id: str, req: RepoRunRequest):
        return Orchestrator(req.repo_path).open_browser_for_login(run_id)

    @app.post("/runs/{run_id}/continue-login")
    def continue_login(run_id: str, req: RepoRunRequest):
        return Orchestrator(req.repo_path).continue_after_login(run_id)

    @app.post("/runs/{run_id}/pause")
    def pause(run_id: str, req: RepoRunRequest):
        return Orchestrator(req.repo_path).pause(run_id)

    @app.post("/runs/{run_id}/resume")
    def resume(run_id: str, req: RepoRunRequest):
        return Orchestrator(req.repo_path).resume(run_id)

    @app.post("/runs/{run_id}/h-inspect")
    def h_inspect(run_id: str, req: HTaskRequest):
        return Orchestrator(req.repo_path).run_h_inspect(run_id, req.task)

    @app.post("/runs/{run_id}/amplify-deploy")
    def amplify_deploy(run_id: str, req: RepoRunRequest):
        return Orchestrator(req.repo_path).run_amplify_deployment(run_id)

    @app.post("/runs/{run_id}/aws-deploy")
    def aws_deploy(run_id: str, req: AWSDeploymentTaskRequest):
        return Orchestrator(req.repo_path).run_aws_deployment_task(run_id, req.task, req.target, req.max_spend_usd)

    @app.get("/runs/{run_id}/amplify-plan")
    def amplify_plan(run_id: str, repo_path: str):
        return Orchestrator(repo_path).get_amplify_plan(run_id)

    @app.get("/runs/{run_id}/aws-plan")
    def aws_plan(run_id: str, repo_path: str):
        return Orchestrator(repo_path).get_aws_plan(run_id)

    @app.post("/h-cleanup")
    def h_cleanup(req: RepoRunRequest):
        return Orchestrator(req.repo_path).cleanup_h_sessions()

    @app.get("/runs/{run_id}/approvals")
    def approvals(run_id: str, repo_path: str):
        return Orchestrator(repo_path).list_approvals(run_id)

    @app.post("/runs/{run_id}/approvals")
    def request_approval(run_id: str, req: ApprovalRequest):
        return Orchestrator(req.repo_path).request_approval(run_id, req.action, req.reason, req.risk_level)

    @app.post("/runs/{run_id}/approval-decision")
    def approval_decision(run_id: str, req: ApprovalDecisionRequest):
        return Orchestrator(req.repo_path).decide_approval(run_id, req.approval_id, req.approved)

    @app.post("/runs/{run_id}/voice")
    def voice(run_id: str, req: VoiceRequest):
        return Orchestrator(req.repo_path).voice_command(run_id, req.text)

    @app.post("/runs/{run_id}/speak")
    def speak(run_id: str, req: VoiceRequest):
        return Orchestrator(req.repo_path).speak(run_id, req.text)

    @app.post("/runs/{run_id}/verify")
    def verify(run_id: str, req: VerifierRequest):
        return Orchestrator(req.repo_path).run_verifier(run_id, req.verifier_name, req.url)

    @app.post("/runs/{run_id}/report")
    def report(run_id: str, req: RepoRunRequest):
        return Orchestrator(req.repo_path).write_report(run_id)

    return app


HTML = r"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Cloud CUA</title>
  <style>
    body { margin: 0; font-family: Inter, system-ui, sans-serif; background: #f3f6f9; color: #152235; }
    header { padding: 16px 24px; background: #0f172a; color: white; display: flex; align-items: center; justify-content: space-between; }
    main { padding: 22px; display: grid; gap: 16px; grid-template-columns: minmax(0, 1.1fr) minmax(320px, .9fr); max-width: 1180px; margin: 0 auto; }
    section { background: white; border: 1px solid #d7dee8; border-radius: 8px; padding: 16px; }
    h2, h3 { margin: 0 0 10px; }
    label { display: block; font-size: 12px; color: #536171; margin-top: 10px; }
    input, select, button, textarea { font: inherit; }
    input, select, textarea { width: 100%; box-sizing: border-box; padding: 8px; border: 1px solid #c7d0db; border-radius: 6px; }
    button { border: 1px solid #1d4ed8; background: #2563eb; color: white; border-radius: 6px; padding: 8px 10px; cursor: pointer; }
    button.secondary { background: white; color: #1d4ed8; }
    button.subtle { background: #f8fafc; color: #334155; border-color: #cbd5e1; }
    button.danger { background: #b91c1c; border-color: #991b1b; }
    .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    .stack { display: grid; gap: 16px; }
    .hero { min-height: 190px; display: flex; flex-direction: column; justify-content: space-between; }
    .eyebrow { text-transform: uppercase; letter-spacing: .08em; font-size: 11px; color: #64748b; font-weight: 700; }
    .status { font-size: 34px; line-height: 1.05; font-weight: 750; letter-spacing: 0; margin: 6px 0; }
    .muted { color: #607084; }
    .pill { display: inline-flex; align-items: center; gap: 6px; border: 1px solid #cbd5e1; background: #f8fafc; border-radius: 999px; padding: 5px 9px; font-size: 12px; color: #334155; }
    .mode { border: 1px solid #cbd5e1; border-radius: 8px; overflow: hidden; display: inline-flex; }
    .mode button { border: 0; border-right: 1px solid #cbd5e1; border-radius: 0; background: white; color: #334155; min-width: 76px; }
    .mode button:last-child { border-right: 0; }
    .mode button.active { background: #111827; color: white; }
    .cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
    .metric { border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; background: #fbfdff; }
    .metric strong { display: block; font-size: 13px; margin-bottom: 6px; }
    pre { white-space: pre-wrap; overflow: auto; background: #0b1020; color: #d1e7ff; padding: 12px; border-radius: 6px; max-height: 460px; }
    details { border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; }
    summary { cursor: pointer; font-weight: 650; }
    .modal-backdrop { position: fixed; inset: 0; backdrop-filter: blur(5px); background: rgba(15,23,42,.45); display: none; align-items: center; justify-content: center; }
    .modal { width: 460px; background: white; border-radius: 8px; padding: 22px; box-shadow: 0 20px 80px rgba(0,0,0,.35); }
    .modal h2 { margin-top: 0; }
    @media (max-width: 860px) { main { grid-template-columns: 1fr; padding: 14px; } .cards { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <header>
    <strong>Cloud CUA</strong>
    <span id="headerState" class="pill">Local dashboard</span>
  </header>
  <main>
    <div class="stack">
      <section class="hero">
        <div>
          <div class="eyebrow">Deployment</div>
          <div id="statusTitle" class="status">Waiting for Codex</div>
          <div id="runSummary" class="muted">Start a run from Codex, or start this local repo for testing.</div>
        </div>
        <div class="row">
          <button id="primaryAction" onclick="startRun()">Start local repo</button>
          <button class="secondary" onclick="openBrowser()">Open cloud login</button>
          <button class="subtle" onclick="pauseRun()">Pause</button>
          <button class="subtle" onclick="resumeRun()">Resume</button>
        </div>
      </section>

      <section>
        <div class="row" style="justify-content:space-between">
          <div>
            <div class="eyebrow">Mode</div>
            <div class="muted">Change how much the agent explains or asks.</div>
          </div>
          <div class="mode">
            <button id="mode-vibe" onclick="setMode('vibe')">Vibe</button>
            <button id="mode-teach" onclick="setMode('teach')">Teach</button>
            <button id="mode-expert" onclick="setMode('expert')">Expert</button>
          </div>
        </div>
      </section>

      <section>
        <h3>Proof</h3>
        <div class="cards">
          <div class="metric"><strong>Cloud identity</strong><span id="identityState" class="muted">Not checked</span></div>
          <div class="metric"><strong>Resources</strong><span id="resourceState" class="muted">Not checked</span></div>
          <div class="metric"><strong>Live app</strong><span id="liveState" class="muted">No URL yet</span></div>
        </div>
        <div class="row" style="margin-top:12px">
          <button class="secondary" onclick="runVerifier()">Run verifier</button>
          <button class="secondary" onclick="writeReport()">Write report</button>
        </div>
      </section>

      <details>
        <summary>Developer tools</summary>
        <label>Repo path</label>
        <input id="repo" />
        <div class="row" style="margin-top:10px">
          <select id="cloud"><option value="aws">AWS</option><option value="gcp">GCP</option></select>
          <select id="mode" style="display:none"><option value="vibe">Vibe</option><option value="teach">Teach</option><option value="expert">Expert</option></select>
        </div>
        <div class="row" style="margin-top:10px">
          <button class="secondary" onclick="showLogin()">Show login gate</button>
          <button class="secondary" onclick="hInspect()">H inspect</button>
        </div>
        <label>Command router</label>
        <textarea id="voiceText" rows="2" placeholder="pause, switch to Teach mode, why Amplify?"></textarea>
        <p><button class="secondary" onclick="sendVoice()">Route command</button></p>
      </details>
    </div>

    <section>
      <div class="row" style="justify-content:space-between">
        <h3>Activity</h3>
        <span id="runIdPill" class="pill">No run</span>
      </div>
      <pre id="events">No events.</pre>
    </section>
  </main>
  <div id="loginModal" class="modal-backdrop">
    <div class="modal">
      <h2>Manual Login Required</h2>
      <p id="loginCopy">Log into AWS in this browser window. Click Continue when done.</p>
      <div class="row">
        <button onclick="continueLogin()">Continue</button>
        <button class="secondary" onclick="hideLogin()">Cancel</button>
      </div>
    </div>
  </div>
<script>
let currentRun = null;
const repoInput = document.getElementById('repo');
initDefaults();

function body(extra={}) { return { repo_path: repoInput.value, ...extra }; }
async function post(url, payload) {
  const r = await fetch(url, { method:'POST', headers:{'content-type':'application/json'}, body: JSON.stringify(payload) });
  if (!r.ok) throw new Error(await r.text());
  return await r.json();
}
async function startRun() {
  localStorage.setItem('cloud_cua_repo', repoInput.value);
  currentRun = await post('/runs', { repo_path: repoInput.value, cloud: cloud.value, mode: activeMode() });
  showLogin();
  await refresh();
}
async function refresh() {
  if (!currentRun) return;
  currentRun = await (await fetch(`/runs/${currentRun.run_id}?repo_path=${encodeURIComponent(repoInput.value)}`)).json();
  statusTitle.textContent = titleForStatus(currentRun.status);
  headerState.textContent = currentRun.status;
  runIdPill.textContent = currentRun.run_id;
  runSummary.innerHTML = `Repo: <b>${shortPath(repoInput.value)}</b><br>Target: <b>${currentRun.target}</b> · Step: <b>${currentRun.current_step}</b>`;
  for (const m of ['vibe','teach','expert']) document.getElementById('mode-'+m).classList.toggle('active', currentRun.mode === m);
  const ev = await (await fetch(`/runs/${currentRun.run_id}/events?repo_path=${encodeURIComponent(repoInput.value)}&limit=80`)).json();
  events.textContent = ev.map(e => `${e.time} ${e.source}:${e.type} ${e.message}`).join('\n');
  updateProof(ev);
}
async function setMode(m) { if (!currentRun) return; await post(`/runs/${currentRun.run_id}/mode`, body({mode:m})); await refresh(); }
async function openBrowser() { if (!currentRun) return; await post(`/runs/${currentRun.run_id}/open-browser`, body()); showLogin(); await refresh(); }
function showLogin() { loginCopy.textContent = cloud.value === 'gcp' ? 'Log into GCP in this browser window. Click Continue when done.' : 'Log into AWS in this browser window. Click Continue when done.'; loginModal.style.display='flex'; }
function hideLogin() { loginModal.style.display='none'; }
async function continueLogin() { if (!currentRun) return; await post(`/runs/${currentRun.run_id}/continue-login`, body()); hideLogin(); await refresh(); }
async function pauseRun() { if (!currentRun) return; await post(`/runs/${currentRun.run_id}/pause`, body()); await refresh(); }
async function resumeRun() { if (!currentRun) return; await post(`/runs/${currentRun.run_id}/resume`, body()); await refresh(); }
async function hInspect() { if (!currentRun) return; await post(`/runs/${currentRun.run_id}/h-inspect`, body()); await refresh(); }
async function runVerifier() { if (!currentRun) return; await post(`/runs/${currentRun.run_id}/verify`, body()); await refresh(); }
async function writeReport() { if (!currentRun) return; await post(`/runs/${currentRun.run_id}/report`, body()); await refresh(); }
async function sendVoice() { if (!currentRun) return; await post(`/runs/${currentRun.run_id}/voice`, body({text: voiceText.value})); voiceText.value=''; await refresh(); }
function activeMode() {
  if (currentRun && currentRun.mode) return currentRun.mode;
  return 'vibe';
}
function titleForStatus(status) {
  return ({created:'Preparing run', waiting_for_login:'Waiting for cloud login', running:'Deployment running', paused:'Paused', verifying:'Verifying deployment', completed:'Deployment complete', blocked:'Needs attention', failed:'Failed'}[status] || 'Deployment status');
}
function shortPath(p) {
  if (!p) return 'No repo selected';
  const parts = p.split(/[\\/]/);
  return parts.slice(-2).join('/');
}
function updateProof(ev) {
  const verifier = ev.filter(e => e.source === 'verifier');
  if (!verifier.length) return;
  identityState.textContent = verifier.some(e => JSON.stringify(e.evidence || {}).includes('aws_identity')) ? 'Checked' : 'Verifier ran';
  resourceState.textContent = verifier.some(e => JSON.stringify(e.evidence || {}).includes('amplify')) ? 'Checked' : 'Pending target result';
}
async function initDefaults() {
  const saved = localStorage.getItem('cloud_cua_repo');
  if (saved) { repoInput.value = saved; return; }
  try {
    const defaults = await (await fetch('/defaults')).json();
    repoInput.value = defaults.repo_path || '';
  } catch {}
}
setInterval(refresh, 3000);
</script>
</body>
</html>
"""

app = create_app()
