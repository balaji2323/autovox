const profileName = document.getElementById("profileName");
const userBadge = document.getElementById("userBadge");
const logoutButton = document.getElementById("logoutButton");
const topSearch = document.getElementById("topSearch");
const refreshAdminButton = document.getElementById("refreshAdminButton");
const candidateTableBody = document.getElementById("candidateTableBody");
const transcriptModal = document.getElementById("transcriptModal");
const transcriptBackdrop = document.getElementById("transcriptBackdrop");
const closeTranscriptModal = document.getElementById("closeTranscriptModal");
const modalCandidateName = document.getElementById("modalCandidateName");
const modalCandidateMeta = document.getElementById("modalCandidateMeta");
const modalTranscriptContent = document.getElementById("modalTranscriptContent");
const viewMode = document.body.dataset.viewMode || "all";

const state = {
  allCandidates: [],
  filteredCandidates: [],
};

logoutButton.addEventListener("click", async () => {
  await fetch("/api/logout", { method: "POST" });
  window.location.href = "/";
});

topSearch.addEventListener("input", () => {
  const query = topSearch.value.trim().toLowerCase();
  const filtered = !query
    ? state.filteredCandidates
    : state.filteredCandidates.filter((candidate) =>
        [candidate.name, candidate.email, candidate.job_role || ""].some((value) => value.toLowerCase().includes(query))
      );
  renderCandidateTable(filtered);
});

refreshAdminButton.addEventListener("click", loadCandidates);
closeTranscriptModal.addEventListener("click", closeTranscriptViewer);
transcriptBackdrop.addEventListener("click", closeTranscriptViewer);

async function hydratePage() {
  const response = await fetch("/api/session");
  const data = await response.json();
  if (!data.authenticated) {
    window.location.href = "/";
    return;
  }

  profileName.textContent = data.user.name;
  userBadge.textContent = `${userBadge.textContent} Logged in as ${data.user.name}.`;
  await loadCandidates();
}

async function loadCandidates() {
  const response = await fetch("/api/candidates");
  const data = await response.json();
  if (!response.ok || !data.ok) {
    candidateTableBody.innerHTML = '<tr><td colspan="7" class="empty-row">Unable to load candidate data.</td></tr>';
    return;
  }

  state.allCandidates = data.candidates || [];
  state.filteredCandidates = applyViewFilter(state.allCandidates);
  renderCandidateTable(state.filteredCandidates);
}

function applyViewFilter(candidates) {
  if (viewMode === "interview_qualified") {
    return candidates.filter((candidate) => normalizeStatus(candidate.interview_result) === "QUALIFIED");
  }

  if (viewMode === "resume_qualified") {
    return candidates.filter((candidate) => normalizeStatus(candidate.ats_decision) === "QUALIFIED");
  }

  if (viewMode === "rejected") {
    return candidates.filter(
      (candidate) =>
        normalizeStatus(candidate.ats_decision) === "NOT QUALIFIED" ||
        normalizeStatus(candidate.interview_result) === "NOT QUALIFIED"
    );
  }

  return candidates;
}

function renderCandidateTable(candidates) {
  if (!candidates.length) {
    candidateTableBody.innerHTML = '<tr><td colspan="7" class="empty-row">No candidates found for this section.</td></tr>';
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

function openTranscriptViewer(candidate) {
  modalCandidateName.textContent = `${candidate.name} Transcript`;
  const interviewScore = candidate.interview_score == null ? "Not scored yet" : `${candidate.interview_score}/5`;
  modalCandidateMeta.textContent = `Result: ${candidate.interview_result} | Interview score: ${interviewScore}`;
  modalTranscriptContent.textContent = candidate.transcript || "No transcript available yet.";
  transcriptModal.classList.remove("hidden");
}

function closeTranscriptViewer() {
  transcriptModal.classList.add("hidden");
}

function getAtsDecision(score) {
  return Number(score) >= 85 ? "QUALIFIED" : "NOT QUALIFIED";
}

function normalizeStatus(value) {
  return String(value || "").trim().toUpperCase();
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
