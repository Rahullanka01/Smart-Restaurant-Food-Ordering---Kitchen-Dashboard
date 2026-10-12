from django import forms

from .models import Order


class CheckoutForm(forms.Form):
    customer_name = forms.CharField(max_length=120, label="Your name")
    phone = forms.CharField(max_length=30, label="Contact number")
    email = forms.EmailField(required=False)
    table_number = forms.IntegerField(min_value=1, max_value=999, label="Table number")

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip()
        if len(phone) < 7:
            raise forms.ValidationError("Enter a valid contact number.")
        return phone


class OrderStatusForm(forms.Form):
    status = forms.ChoiceField(choices=Order.Status.choices, label="Update status")