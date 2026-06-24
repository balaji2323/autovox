import json

from django.conf import settings
from django.core.mail import send_mail
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST


REQUIRED_FIELDS = {
    "fullName": "Full Name",
    "businessName": "Business Name",
    "phone": "Phone Number",
    "email": "Email Address",
    "businessType": "Business Type",
    "message": "Message",
}


def home(request):
    return render(request, "index.html")


@require_POST
def contact_enquiry(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid form data."}, status=400)

    missing = [label for key, label in REQUIRED_FIELDS.items() if not payload.get(key, "").strip()]
    if missing:
        return JsonResponse(
            {"success": False, "message": f"Please complete: {', '.join(missing)}."},
            status=400,
        )

    subject = f"New AutoVox AI enquiry from {payload['fullName'].strip()}"
    message = "\n".join(
        [
            "New enquiry from the AutoVox AI website:",
            "",
            f"Full Name: {payload['fullName'].strip()}",
            f"Business Name: {payload['businessName'].strip()}",
            f"Phone Number: {payload['phone'].strip()}",
            f"Email Address: {payload['email'].strip()}",
            f"Business Type: {payload['businessType'].strip()}",
            "",
            "Message:",
            payload["message"].strip(),
        ]
    )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.AUTOVOX_ENQUIRY_EMAIL],
            fail_silently=False,
        )
    except Exception:
        return JsonResponse(
            {
                "success": False,
                "message": "Sorry, we could not send your enquiry right now. Please try again later.",
            },
            status=502,
        )

    return JsonResponse(
        {"success": True, "message": "Thank you! Your enquiry has been sent successfully."}
    )
