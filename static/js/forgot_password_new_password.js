const forgotPasswordResetForm = document.getElementById("forgotPasswordResetForm");
const forgotNewPasswordInput = document.getElementById("forgotNewPasswordInput");
const forgotConfirmPasswordInput = document.getElementById("forgotConfirmPasswordInput");
const forgotPasswordMessage = document.getElementById("forgotPasswordMessage");

forgotPasswordResetForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  forgotPasswordMessage.textContent = "Updating password...";

  const response = await fetch("/api/forgot-password/reset", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      new_password: forgotNewPasswordInput.value,
      confirm_password: forgotConfirmPasswordInput.value,
    }),
  });
  const data = await response.json();

  if (!response.ok || !data.ok) {
    forgotPasswordMessage.textContent = data.error || "Unable to reset password.";
    return;
  }

  forgotPasswordMessage.textContent = data.message || "Password reset successful.";
  setTimeout(() => {
    window.location.href = data.redirect_url || "/";
  }, 1200);
});
