from django.urls import path
from django.views.generic import TemplateView

page = lambda name: TemplateView.as_view(template_name=f"core/{name}.html")

urlpatterns = [
    path("", page("home"), name="home"),
    path("catalog/", page("catalog"), name="catalog"),
    path("cart/", page("cart"), name="cart"),
    path("favorites/", page("favorites"), name="favorites"),
    path("about/", page("about"), name="about"),
    path("contacts/", page("contacts"), name="contacts"),
]
