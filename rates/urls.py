from django.urls import path

from . import views

app_name = "rates"

urlpatterns = [
    path("", views.index, name="index"),
    path("api/rates/", views.rates_api, name="api"),
]