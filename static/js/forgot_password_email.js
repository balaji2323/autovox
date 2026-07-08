const forgotPasswordRequestForm = document.getElementById("forgotPasswordRequestForm");
const forgotEmailInput = document.getElementById("forgotEmailInput");
const forgotPasswordMessage = document.getElementById("forgotPasswordMessage");

forgotPasswordRequestForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  forgotPasswordMessage.textContent = "Sending OTP to your email...";

  const response = await fetch("/api/forgot-password/request", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: forgotEmailInput.value.trim() }),
  });
  const data = await response.json();

  if (!response.ok || !data.ok) {
    forgotPasswordMessage.textContent = data.error || "Unable to send OTP.";
    return;
  }

  window.location.href = data.redirect_url || "/forgot-password/verify";
});
