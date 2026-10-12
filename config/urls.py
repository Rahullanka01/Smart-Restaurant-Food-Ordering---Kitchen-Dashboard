from django.contrib import admin
from django.urls import include, path

handler404 = "restaurant.views.custom_404"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("restaurant.urls")),
]