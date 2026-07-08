const profileName = document.getElementById("profileName");
const userBadge = document.getElementById("userBadge");
const logoutButton = document.getElementById("logoutButton");
const uploadForm = document.getElementById("uploadForm");
const resumeFiles = document.getElementById("resumeFiles");
const selectedFilesLabel = document.getElementById("selectedFilesLabel");
const uploadStatus = document.getElementById("uploadStatus");
const analysisForm = document.getElementById("analysisForm");
const jobDescription = document.getElementById("jobDescription");
const systemLog = document.getElementById("systemLog");
const analysisResults = document.getElementById("analysisResults");

let currentUser = null;
let lastAnalysisResults = [];

resumeFiles.addEventListener("change", () => {
  const files = [...resumeFiles.files].map((file) => file.name);
  selectedFilesLabel.textContent = files.length ? files.join(", ") : "No files selected";
});

logoutButton.addEventListener("click", async () => {
  await fetch("/api/logout", { method: "POST" });
  window.location.href = "/";
});

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  uploadStatus.textContent = "Uploading resumes...";

  const formData = new FormData();
  [...resumeFiles.files].forEach((file) => formData.append("resumes", file));

  const response = await fetch("/api/upload-resumes", {
    method: "POST",
    body: formData,
  });
  const data = await response.json();

  if (!response.ok || !data.ok) {
    uploadStatus.textContent = data.error || "Upload failed.";
    return;
  }

  uploadStatus.textContent = `${data.message} Files: ${data.files.join(", ")}`;
  appendLogs([data.message]);
});

analysisForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  analysisResults.innerHTML = '<p class="empty-state">Analyzing resumes...</p>';
  appendLogs(["Starting ATS analysis..."]);

  const response = await fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_description: jobDescription.value }),
  });
  const data = await response.json();

  if (!response.ok || !data.ok) {
    appendLogs([data.error || "Analysis failed."]);
    analysisResults.innerHTML = `<p class="empty-state">${escapeHtml(data.error || "Analysis failed.")}</p>`;
    return;
  }

  lastAnalysisResults = data.results || [];
  appendLogs(data.logs || []);
  renderResults(lastAnalysisResults);
});

async function hydratePage() {
  const response = await fetch("/api/session");
  const data = await response.json();
  if (!data.authenticated) {
    window.location.href = "/";
    return;
  }

  currentUser = data.user;
  profileName.textContent = currentUser.name;
  userBadge.textContent = `Upload resumes, create job analysis, and monitor analysis activity from one page, ${currentUser.name}.`;
  await loadExistingResults();
}

async function loadExistingResults() {
  const response = await fetch("/api/dashboard");
  const data = await response.json();
  if (!response.ok || !data.ok) {
    appendLogs([data.error || "Unable to load dashboard data."]);
    return;
  }

  renderResults(data.analysis_results || []);
}

function appendLogs(lines) {
  const current = systemLog.textContent.trim() === "System ready." ? [] : systemLog.textContent.split("\n");
  const timestamped = lines.map((line) => `[${new Date().toLocaleTimeString()}] ${line}`);
  const next = [...current.filter(Boolean), ...timestamped];
  systemLog.textContent = next.length ? next.join("\n") : "System ready.";
}

function renderResults(results) {
  if (!results.length) {
    analysisResults.innerHTML = '<p class="empty-state">No candidates were returned from the latest analysis.</p>';
    return;
  }

  analysisResults.innerHTML = results
    .map(
      (result) => `
        <article class="result-card">
          <h4>${escapeHtml(result.name)} <span class="score-pill">${result.score}</span></h4>
          <p><strong>Email:</strong> ${escapeHtml(result.email)}</p>
          <p><strong>Phone:</strong> ${escapeHtml(result.phone || "Not available")}</p>
          <p><strong>ATS Decision:</strong> <span class="status-pill ${getStatusMeta(result.ats_decision || getAtsDecision(result.score)).className}">${escapeHtml(getStatusMeta(result.ats_decision || getAtsDecision(result.score)).label)}</span></p>
          <p><strong>Interview Result:</strong> <span class="status-pill ${getStatusMeta(result.interview_result || result.qualification_status || "Pending").className}">${escapeHtml(getStatusMeta(result.interview_result || result.qualification_status || "Pending").label)}</span></p>
          ${result.email_status ? `<p><strong>Email Status:</strong> ${escapeHtml(result.email_status)}</p>` : ""}
          ${result.call_status ? `<p><strong>Call Status:</strong> ${escapeHtml(result.call_status)}</p>` : ""}
          <p><strong>Summary:</strong> ${escapeHtml(result.reasoning || result.transcript_preview || "No summary returned.")}</p>
        </article>
      `
    )
    .join("");
}

function getAtsDecision(score) {
  return Number(score) >= 85 ? "QUALIFIED" : "NOT QUALIFIED";
}

function getStatusMeta(status) {
  const normalized = String(status || "Pending").trim();
  const key = normalized.toUpperCase();
  const statusMap = {
    QUALIFIED: { className: "high", label: "Qualified" },
    "NOT QUALIFIED": { className: "low", label: "Not Qualified" },
    "IN PROGRESS": { className: "medium", label: "Interview In Progress" },
    "INTERVIEW IN PROGRESS": { className: "medium", label: "Interview In Progress" },
    PENDING: { className: "medium", label: "Pending Interview" },
    "AWAITING INTERVIEW": { className: "medium", label: "Awaiting Interview" },
  };
  return statusMap[key] || { className: "medium", label: normalized };
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

hydratePage();
