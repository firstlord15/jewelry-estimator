from django.urls import path

from . import views

urlpatterns = [
    path("catalog/", views.product_list, name="catalog"),
    # path("catalog/search/", views.search, name="catalog_search"),
    path("catalog/product/<slug:slug>/", views.product_detail, name="product"),
    path("catalog/<slug:category_slug>/", views.product_list, name="catalog_category"),
]
