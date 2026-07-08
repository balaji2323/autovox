const state = {
  user: null,
  allCandidates: [],
  lastAnalysisResults: [],
};

const loginScreen = document.getElementById("loginScreen");
const dashboard = document.getElementById("dashboard");
const loginForm = document.getElementById("loginForm");
const loginError = document.getElementById("loginError");
const logoutButton = document.getElementById("logoutButton");
const navChips = [...document.querySelectorAll("[data-scroll-target]")];
const portalNavItems = [...document.querySelectorAll(".portal-nav-item[data-scroll-target]")];
const topSearch = document.getElementById("topSearch");
const userBadge = document.getElementById("userBadge");
const profileName = document.getElementById("profileName");

const uploadForm = document.getElementById("uploadForm");
const resumeFiles = document.getElementById("resumeFiles");
const selectedFilesLabel = document.getElementById("selectedFilesLabel");
const uploadStatus = document.getElementById("uploadStatus");
const analysisForm = document.getElementById("analysisForm");
const jobDescription = document.getElementById("jobDescription");
const systemLog = document.getElementById("systemLog");
const analysisResults = document.getElementById("analysisResults");

const refreshAdminButton = document.getElementById("refreshAdminButton");
const candidateTableBody = document.getElementById("candidateTableBody");
const recentActivity = document.getElementById("recentActivity");
const overviewChart = document.getElementById("overviewChart");
const distributionChart = document.getElementById("distributionChart");

const jobsPosted = document.getElementById("jobsPosted");
const resumesUploaded = document.getElementById("resumesUploaded");
const interviewsCompleted = document.getElementById("interviewsCompleted");
const hiresMade = document.getElementById("hiresMade");
const transcriptModal = document.getElementById("transcriptModal");
const transcriptBackdrop = document.getElementById("transcriptBackdrop");
const closeTranscriptModal = document.getElementById("closeTranscriptModal");
const modalCandidateName = document.getElementById("modalCandidateName");
const modalCandidateMeta = document.getElementById("modalCandidateMeta");
const modalTranscriptContent = document.getElementById("modalTranscriptContent");

navChips.forEach((chip) => {
  chip.addEventListener("click", () => {
    const target = document.getElementById(chip.dataset.scrollTarget);
    if (target) {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  });
});

portalNavItems.forEach((item) => {
  item.addEventListener("click", () => {
    portalNavItems.forEach((navItem) => navItem.classList.remove("active"));
    item.classList.add("active");
    const target = document.getElementById(item.dataset.scrollTarget);
    if (target) {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  });
});

if (resumeFiles && selectedFilesLabel) {
  resumeFiles.addEventListener("change", () => {
    const files = [...resumeFiles.files].map((file) => file.name);
    selectedFilesLabel.textContent = files.length ? files.join(", ") : "No files selected";
  });
}

if (topSearch && candidateTableBody) {
  topSearch.addEventListener("input", () => {
    const query = topSearch.value.trim().toLowerCase();
    const filtered = !query
      ? state.allCandidates
      : state.allCandidates.filter((candidate) =>
          [candidate.name, candidate.email].some((value) => value.toLowerCase().includes(query))
        );
    renderCandidateTable(filtered);
  });
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  loginError.textContent = "";

  const payload = {
    username: document.getElementById("usernameInput").value.trim(),
    password: document.getElementById("passwordInput").value,
  };

  const response = await fetch("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();

  if (!response.ok || !data.ok) {
    loginError.textContent = data.error || "Unable to sign in.";
    return;
  }

  state.user = data.user;
  showDashboard();
});

logoutButton.addEventListener("click", async () => {
  await fetch("/api/logout", { method: "POST" });
  state.user = null;
  state.allCandidates = [];
  state.lastAnalysisResults = [];
  dashboard.classList.add("hidden");
  loginScreen.classList.remove("hidden");
  loginForm.reset();
  if (selectedFilesLabel) {
    selectedFilesLabel.textContent = "No files selected";
  }
  if (uploadStatus) {
    uploadStatus.textContent = "";
  }
});

if (uploadForm) {
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
    await loadDashboard();
  });
}

if (analysisForm) {
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
    analysisResults.innerHTML = `<p class="empty-state">${data.error || "Analysis failed."}</p>`;
    return;
  }

    state.lastAnalysisResults = data.results || [];
    appendLogs(data.logs || []);
    renderResults(state.lastAnalysisResults);
    await loadDashboard();
  });
}

if (refreshAdminButton) {
  refreshAdminButton.addEventListener("click", loadDashboard);
}
if (closeTranscriptModal) {
  closeTranscriptModal.addEventListener("click", closeTranscriptViewer);
}
if (transcriptBackdrop) {
  transcriptBackdrop.addEventListener("click", closeTranscriptViewer);
}

async function hydrateSession() {
  const response = await fetch("/api/session");
  const data = await response.json();
  if (!data.authenticated) {
    return;
  }
  state.user = data.user;
  showDashboard();
}

function showDashboard() {
  loginScreen.classList.add("hidden");
  dashboard.classList.remove("hidden");
  userBadge.textContent = `Find, evaluate, and hire the best talent with your AI-powered recruitment workspace, ${state.user.name}.`;
  profileName.textContent = state.user.name;
  loadDashboard();
}

async function loadDashboard() {
  const response = await fetch("/api/dashboard");
  const data = await response.json();

  if (!response.ok || !data.ok) {
    appendLogs([data.error || "Unable to load dashboard data."]);
    return;
  }

  if (jobsPosted) {
    jobsPosted.textContent = data.stats.jobs_posted;
  }
  if (resumesUploaded) {
    resumesUploaded.textContent = data.stats.resumes_uploaded;
  }
  if (interviewsCompleted) {
    interviewsCompleted.textContent = data.stats.interviews_completed;
  }
  if (hiresMade) {
    hiresMade.textContent = data.stats.hires_made;
  }

  if (overviewChart) {
    overviewChart.src = data.charts.overview;
  }
  if (distributionChart) {
    distributionChart.src = data.charts.distribution;
  }

  state.allCandidates = data.candidates || [];
  renderCandidateTable(state.allCandidates);
  renderRecentActivity(data.recent_activity || []);
  renderResults(state.lastAnalysisResults.length ? state.lastAnalysisResults : data.analysis_results || []);
}

function appendLogs(lines) {
  if (!systemLog) {
    return;
  }
  const current = systemLog.textContent.trim() === "System ready." ? [] : systemLog.textContent.split("\n");
  const timestamped = lines.map((line) => `[${new Date().toLocaleTimeString()}] ${line}`);
  const next = [...current.filter(Boolean), ...timestamped];
  systemLog.textContent = next.length ? next.join("\n") : "System ready.";
}

function renderResults(results) {
  if (!analysisResults) {
    return;
  }
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

function renderRecentActivity(items) {
  if (!recentActivity) {
    return;
  }
  recentActivity.innerHTML = items
    .map(
      (item) => `
        <article class="activity-item">
          <strong>${escapeHtml(item.title)}</strong>
          <p>${escapeHtml(item.detail)}</p>
          <span class="activity-time">${escapeHtml(item.time)}</span>
        </article>
      `
    )
    .join("");
}

function renderCandidateTable(candidates) {
  if (!candidateTableBody) {
    return;
  }
  if (!candidates.length) {
    candidateTableBody.innerHTML = '<tr><td colspan="7" class="empty-row">No candidate records found yet.</td></tr>';
    return;
  }

  candidateTableBody.innerHTML = candidates
    .map((candidate) => {
      const atsDecision = getStatusMeta(candidate.ats_decision || getAtsDecision(candidate.score));
      const interviewDecision = getStatusMeta(candidate.interview_result || candidate.qualification_status || "Pending");
      const reason = candidate.interview_reason || candidate.transcript_preview;
      const preview = reason
        ? `<div class="candidate-subline">Reason: ${escapeHtml(reason)}</div>`
        : "";
      const actionLabel = candidate.has_transcript ? "Transcript" : "Pending";
      return `
        <tr>
          <td>${escapeHtml(candidate.name)}${preview}</td>
          <td>${escapeHtml(candidate.job_role || "General Role")}</td>
          <td>${escapeHtml(candidate.email)}</td>
          <td><span class="score-pill">${candidate.score}</span></td>
          <td><span class="status-pill ${atsDecision.className}">${escapeHtml(atsDecision.label)}</span></td>
          <td><span class="status-pill ${interviewDecision.className}">${escapeHtml(interviewDecision.label)}</span></td>
          <td><button class="table-action" type="button" data-candidate-id="${candidate.id}" ${candidate.has_transcript ? "" : "disabled"}>${actionLabel}</button></td>
        </tr>
      `;
    })
    .join("");

  candidateTableBody.querySelectorAll("[data-candidate-id]").forEach((button) => {
    button.addEventListener("click", () => {
      const candidate = state.allCandidates.find((item) => String(item.id) === button.dataset.candidateId);
      if (candidate) {
        openTranscriptViewer(candidate);
      }
    });
  });
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

function openTranscriptViewer(candidate) {
  if (!transcriptModal || !modalCandidateName || !modalCandidateMeta || !modalTranscriptContent) {
    return;
  }
  modalCandidateName.textContent = `${candidate.name} Transcript`;
  const interviewScore = candidate.interview_score == null ? "Not scored yet" : `${candidate.interview_score}/5`;
  modalCandidateMeta.textContent = `Result: ${candidate.interview_result} | Interview score: ${interviewScore}`;
  modalTranscriptContent.textContent = candidate.transcript || "No transcript available yet.";
  transcriptModal.classList.remove("hidden");
}

function closeTranscriptViewer() {
  if (!transcriptModal) {
    return;
  }
  transcriptModal.classList.add("hidden");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

hydrateSession();
