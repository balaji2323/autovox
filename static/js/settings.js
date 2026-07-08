const logoutButton = document.getElementById("logoutButton");
const profileName = document.getElementById("profileName");
const userBadge = document.getElementById("userBadge");
const settingsStatus = document.getElementById("settingsStatus");

const recruiterNamePreview = document.getElementById("recruiterNamePreview");
const recruiterRolePreview = document.getElementById("recruiterRolePreview");

const profileForm = document.getElementById("profileForm");
const recruiterName = document.getElementById("recruiterName");
const recruiterRole = document.getElementById("recruiterRole");
const recruiterEmail = document.getElementById("recruiterEmail");
const recruiterPhone = document.getElementById("recruiterPhone");
const recruiterCompany = document.getElementById("recruiterCompany");
const recruiterLocation = document.getElementById("recruiterLocation");
const recruiterExperience = document.getElementById("recruiterExperience");

const credentialsForm = document.getElementById("credentialsForm");
const recruiterUsername = document.getElementById("recruiterUsername");
const recruiterPassword = document.getElementById("recruiterPassword");
const recruiterConfirmPassword = document.getElementById("recruiterConfirmPassword");
const recruiterAccessLevel = document.getElementById("recruiterAccessLevel");
const recruiterStatus = document.getElementById("recruiterStatus");

logoutButton.addEventListener("click", async () => {
  await fetch("/api/logout", { method: "POST" });
  window.location.href = "/";
});

profileForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  setStatus("Saving recruiter profile...", "info");

  const response = await fetch("/api/recruiter/profile", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: recruiterName.value.trim(),
      role: recruiterRole.value.trim(),
      email: recruiterEmail.value.trim(),
      phone: recruiterPhone.value.trim(),
      company: recruiterCompany.value.trim(),
      location: recruiterLocation.value.trim(),
      experience: recruiterExperience.value.trim(),
    }),
  });
  const data = await response.json();

  if (!response.ok || !data.ok) {
    setStatus(data.error || "Unable to save recruiter profile.", "error");
    return;
  }

  applyUser(data.user);
  setStatus(data.message || "Recruiter profile updated successfully.", "success");
});

credentialsForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  setStatus("Updating login credentials...", "info");

  const response = await fetch("/api/recruiter/credentials", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      username: recruiterUsername.value.trim(),
      password: recruiterPassword.value,
      confirm_password: recruiterConfirmPassword.value,
    }),
  });
  const data = await response.json();

  if (!response.ok || !data.ok) {
    setStatus(data.error || "Unable to update login credentials.", "error");
    return;
  }

  recruiterPassword.value = "";
  recruiterConfirmPassword.value = "";
  applyUser(data.user);
  setStatus(data.message || "Login credentials updated successfully.", "success");
});

async function hydratePage() {
  const response = await fetch("/api/session");
  const data = await response.json();
  if (!data.authenticated) {
    window.location.href = "/";
    return;
  }

  applyUser(data.user);
}

function applyUser(user) {
  profileName.textContent = user.name || "Recruiter";
  userBadge.textContent = `Update recruiter details, username, and password from the portal itself for ${user.name}.`;
  recruiterNamePreview.textContent = user.name || "Recruiter";
  recruiterRolePreview.textContent = user.role || "Recruiter";

  recruiterName.value = user.name || "";
  recruiterRole.value = user.role || "";
  recruiterEmail.value = user.email || "";
  recruiterPhone.value = user.phone || "";
  recruiterCompany.value = user.company || "";
  recruiterLocation.value = user.location || "";
  recruiterExperience.value = user.experience || "";

  recruiterUsername.value = user.username || "";
  recruiterAccessLevel.textContent = user.access_level || "Administrator";
  recruiterStatus.textContent = user.status || "Active";
}

function setStatus(message, type) {
  settingsStatus.textContent = message;
  settingsStatus.className = `settings-status ${type}`;
}

hydratePage();
