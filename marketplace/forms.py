from django import forms

from core.forms import StyledForm, UGXField, campus_field
from core.models import Category

from .models import Listing


class ListingForm(StyledForm, forms.Form):
    title = forms.CharField(min_length=4, max_length=90, help_text="Say what it is: brand, model, size. E.g. “HP EliteBook 840, Core i5, 8GB”.")
    category = forms.ModelChoiceField(queryset=Category.objects.none(), empty_label="Choose a category", error_messages={"required": "Choose a category."})
    condition = forms.ChoiceField(choices=[("", "Choose condition")] + list(Listing.Condition.choices), error_messages={"required": "Choose the item's condition."})
    description = forms.CharField(min_length=10, max_length=3000, widget=forms.Textarea(attrs={"rows": 5}),
                                  help_text="Include age, any faults, what's included, and why you're selling.")
    price_ugx = UGXField(label="Price (UGX)", max_value=200_000_000, help_text="Whole shillings, e.g. 450000. Enter 0 to give it away.")
    is_negotiable = forms.BooleanField(required=False, label="Price is negotiable")
    campus = campus_field(label="Campus")
    meetup_note = forms.CharField(required=False, max_length=140, label="Preferred meet-up spot", help_text="Pick a busy, public place on campus.",
                                  widget=forms.TextInput(attrs={"placeholder": "e.g. Main Library steps"}))

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["category"].queryset = Category.objects.filter(module="marketplace", is_active=True)


class MarkSoldForm(StyledForm, forms.Form):
    buyer = forms.ChoiceField(required=False, label="Who bought it?")
    final_price = UGXField(label="Final price (UGX)", max_value=200_000_000)

    def __init__(self, *a, contacts=(), **kw):
        super().__init__(*a, **kw)
        self.fields["buyer"].choices = [("", "Someone not on CampusHub / prefer not to say")] + [(str(c.pk), c.full_name) for c in contacts]
