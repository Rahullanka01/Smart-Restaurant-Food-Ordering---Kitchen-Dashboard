from django import template

from restaurant.currency import format_inr


register = template.Library()
register.filter("inr", format_inr)