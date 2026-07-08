const forgotPasswordVerifyForm = document.getElementById("forgotPasswordVerifyForm");
const forgotOtpInput = document.getElementById("forgotOtpInput");
const forgotPasswordMessage = document.getElementById("forgotPasswordMessage");

forgotPasswordVerifyForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  forgotPasswordMessage.textContent = "Verifying OTP...";

  const response = await fetch("/api/forgot-password/verify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ otp: forgotOtpInput.value.trim() }),
  });
  const data = await response.json();

  if (!response.ok || !data.ok) {
    forgotPasswordMessage.textContent = data.error || "Unable to verify OTP.";
    return;
  }

  window.location.href = data.redirect_url || "/forgot-password/new-password";
});
