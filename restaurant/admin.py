from django.contrib import admin

from .currency import format_inr
from .branding import BRAND_NAME
from .models import Category, MenuItem, Order, OrderItem

admin.site.site_header = BRAND_NAME
admin.site.site_title = f"{BRAND_NAME} Admin"
admin.site.index_title = "Restaurant operations"


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "display_order")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("display_order", "name")


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price_inr", "is_vegetarian", "is_available")
    list_filter = ("category", "is_vegetarian", "is_available")
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}

    @admin.display(description="Price (INR)", ordering="price")
    def price_inr(self, obj):
        return format_inr(obj.price)

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "price":
            kwargs["label"] = "Price (INR)"
        return super().formfield_for_dbfield(db_field, request, **kwargs)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = ("item_name", "quantity", "unit_price_inr")
    readonly_fields = fields

    @admin.display(description="Unit price (INR)")
    def unit_price_inr(self, obj):
        return format_inr(obj.unit_price)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("public_id", "customer_name", "table_number", "status", "total_inr", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("customer_name", "phone", "public_id")
    readonly_fields = ("public_id", "subtotal_inr", "tax_inr", "total_inr", "created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("public_id", "customer_name", "phone", "email", "table_number", "status")}),
        ("Amounts (INR)", {"fields": ("subtotal_inr", "tax_inr", "total_inr")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
    inlines = (OrderItemInline,)

    @admin.display(description="Subtotal (INR)", ordering="subtotal")
    def subtotal_inr(self, obj):
        return format_inr(obj.subtotal)

    @admin.display(description="Tax (INR)", ordering="tax")
    def tax_inr(self, obj):
        return format_inr(obj.tax)

    @admin.display(description="Total (INR)", ordering="total")
    def total_inr(self, obj):
        return format_inr(obj.total)