from django.urls import path

from . import views

app_name = "restaurant"

urlpatterns = [
    path("", views.home, name="home"),
    path("cart/", views.cart, name="cart"),
    path("checkout/", views.checkout, name="checkout"),
    path("orders/<uuid:public_id>/", views.order_confirmation, name="order_confirmation"),
    path("track/", views.track_order, name="track_order"),
    path("kitchen/", views.kitchen_dashboard, name="kitchen"),
    path("kitchen/orders/<int:order_id>/status/", views.update_order_status, name="update_order_status"),
]