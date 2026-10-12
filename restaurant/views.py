import json
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.staticfiles.storage import staticfiles_storage
from django.db import transaction
from django.db.models import Prefetch
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import CheckoutForm, OrderStatusForm
from .models import Category, MenuItem, Order, OrderItem


def menu_payload(items):
    return [
        {
            "id": item.pk,
            "name": item.name,
            "price": str(item.price),
            "image": staticfiles_storage.url(item.image_path) if item.image_path else item.image_url,
            "category": item.category.name,
        }
        for item in items
    ]


def home(request):
    categories = Category.objects.all()
    items = MenuItem.objects.select_related("category")
    selected_category = request.GET.get("category", "")
    if selected_category:
        items = items.filter(category__slug=selected_category)
    all_items = MenuItem.objects.filter(is_available=True).select_related("category")
    return render(
        request,
        "restaurant/home.html",
        {
            "categories": categories,
            "items": items,
            "selected_category": selected_category,
            "menu_items_json": menu_payload(all_items),
        },
    )


def cart(request):
    items = list(MenuItem.objects.filter(is_available=True).select_related("category"))
    return render(request, "restaurant/cart.html", {"menu_items_json": menu_payload(items)})


def checkout(request):
    if request.method == "POST":
        form = CheckoutForm(request.POST)
        try:
            raw_cart = json.loads(request.POST.get("cart_json", "{}"))
            cart_data = _validated_cart(raw_cart)
        except (json.JSONDecodeError, TypeError, ValueError):
            cart_data = {}
            form.add_error(None, "Your cart could not be read. Please review it and try again.")

        request.session["cart"] = cart_data
        if not cart_data:
            form.add_error(None, "Your cart is empty. Add an available menu item before checking out.")

        if form.is_valid() and cart_data:
            items_by_id = MenuItem.objects.filter(pk__in=cart_data, is_available=True).select_related("category")
            items_by_id = {str(item.pk): item for item in items_by_id}
            if len(items_by_id) != len(cart_data):
                form.add_error(None, "One or more items are no longer available. Please update your cart.")
            else:
                with transaction.atomic():
                    subtotal = sum(
                        (items_by_id[item_id].price * quantity for item_id, quantity in cart_data.items()),
                        Decimal("0.00"),
                    )
                    tax_rate = Decimal(settings.ORDER_TAX_RATE)
                    tax = (subtotal * tax_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    order = Order.objects.create(
                        **form.cleaned_data,
                        subtotal=subtotal,
                        tax=tax,
                        total=subtotal + tax,
                    )
                    OrderItem.objects.bulk_create(
                        [
                            OrderItem(
                                order=order,
                                menu_item=items_by_id[item_id],
                                item_name=items_by_id[item_id].name,
                                quantity=quantity,
                                unit_price=items_by_id[item_id].price,
                            )
                            for item_id, quantity in cart_data.items()
                        ]
                    )
                request.session.pop("cart", None)
                return redirect("restaurant:order_confirmation", public_id=order.public_id)
    else:
        form = CheckoutForm()
    available_items = list(MenuItem.objects.filter(is_available=True).select_related("category"))
    return render(
        request,
        "restaurant/checkout.html",
        {"form": form, "menu_items_json": menu_payload(available_items)},
    )


def _validated_cart(raw_cart):
    if not isinstance(raw_cart, dict) or len(raw_cart) > 50:
        raise ValueError("Invalid cart")
    cart_data = {}
    for item_id, quantity in raw_cart.items():
        if not str(item_id).isdigit() or isinstance(quantity, bool) or not isinstance(quantity, int):
            raise ValueError("Invalid cart item")
        if quantity < 1 or quantity > 99:
            raise ValueError("Invalid quantity")
        cart_data[str(int(item_id))] = quantity
    return cart_data


def order_confirmation(request, public_id):
    order = get_object_or_404(Order.objects.prefetch_related("items"), public_id=public_id)
    return render(request, "restaurant/order_confirmation.html", {"order": order})


def track_order(request):
    order = None
    lookup_error = ""
    submitted_id = request.GET.get("order_id", "").strip()
    if submitted_id:
        try:
            public_id = UUID(submitted_id)
        except ValueError:
            lookup_error = "Enter a valid order ID."
        else:
            order = Order.objects.prefetch_related("items").filter(public_id=public_id).first()
            if order is None:
                lookup_error = "We couldn't find an order with that ID."
    return render(
        request,
        "restaurant/track_order.html",
        {
            "order": order,
            "lookup_error": lookup_error,
            "submitted_id": submitted_id,
            "status_choices": Order.Status.choices,
        },
    )


@staff_member_required
def kitchen_dashboard(request):
    orders = Order.objects.exclude(status=Order.Status.COMPLETED).prefetch_related(
        Prefetch("items", queryset=OrderItem.objects.select_related("menu_item"))
    )
    return render(request, "restaurant/kitchen.html", {"orders": orders, "status_choices": Order.Status.choices})


@staff_member_required
def update_order_status(request, order_id):
    if request.method != "POST":
        raise Http404
    order = get_object_or_404(Order, pk=order_id)
    form = OrderStatusForm(request.POST)
    if form.is_valid():
        order.status = form.cleaned_data["status"]
        order.updated_at = timezone.now()
        order.save(update_fields=["status", "updated_at"])
        messages.success(request, f"Order {str(order.public_id)[:8]} updated to {order.get_status_display()}.")
    else:
        messages.error(request, "Choose a valid order status.")
    return redirect("restaurant:kitchen")


def custom_404(request, exception):
    return render(request, "404.html", status=404)