from django.urls import path

from . import views


urlpatterns = [
    path("", views.home, name="home"),
    path("api/contact/", views.contact_enquiry, name="contact_enquiry"),
]
