const navToggle = document.querySelector(".nav-toggle");
const navLinks = document.querySelector(".nav-links");
const contactForm = document.querySelector("#contact-form");
const formMessage = document.querySelector("#form-message");

if (navToggle && navLinks) {
    navToggle.addEventListener("click", () => {
        const isOpen = navLinks.classList.toggle("is-open");
        navToggle.setAttribute("aria-expanded", String(isOpen));
    });

    navLinks.querySelectorAll("a").forEach((link) => {
        link.addEventListener("click", () => {
            navLinks.classList.remove("is-open");
            navToggle.setAttribute("aria-expanded", "false");
        });
    });
}

function getCsrfToken() {
    const tokenInput = document.querySelector("[name=csrfmiddlewaretoken]");
    return tokenInput ? tokenInput.value : "";
}

if (contactForm && formMessage) {
    contactForm.addEventListener("submit", async (event) => {
        event.preventDefault();

        const submitButton = contactForm.querySelector("button[type=submit]");
        const formData = new FormData(contactForm);
        const payload = Object.fromEntries(formData.entries());

        formMessage.textContent = "";
        formMessage.classList.remove("error");
        submitButton.disabled = true;
        submitButton.textContent = "Sending...";

        try {
            const response = await fetch("/api/contact/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCsrfToken(),
                },
                body: JSON.stringify(payload),
            });

            const result = await response.json();
            formMessage.textContent = result.message || "Thank you! Your enquiry has been sent successfully.";

            if (!response.ok || !result.success) {
                formMessage.classList.add("error");
                return;
            }

            contactForm.reset();
        } catch (error) {
            formMessage.textContent = "Sorry, we could not send your enquiry right now. Please try again later.";
            formMessage.classList.add("error");
        } finally {
            submitButton.disabled = false;
            submitButton.textContent = "Submit Enquiry";
        }
    });
}
