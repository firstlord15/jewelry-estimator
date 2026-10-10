from django.urls import path

from . import views

urlpatterns = [
    path("calculator/", views.index, name="calculator"),
    path("api/rates/", views.rates_api, name="rates_api"),
]
