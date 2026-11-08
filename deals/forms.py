from django import forms

from core.forms import EndOfDayField, StyledForm, UGXField, UgPhoneField
from core.models import Campus

from .models import Business, Deal


class BusinessForm(StyledForm, forms.Form):
    name = forms.CharField(label="Business name", min_length=2, max_length=80)
    kind = forms.ChoiceField(label="Type of business", choices=[("", "Choose a type")] + list(Business.Kind.choices))
    description = forms.CharField(label="About your business", min_length=20, max_length=1500, widget=forms.Textarea(attrs={"rows": 4}),
                                  help_text="What you offer students, opening hours, and what makes you different.")
    address = forms.CharField(label="Address / location", min_length=5, max_length=160, widget=forms.TextInput(attrs={"placeholder": "e.g. Wandegeya, opposite the market"}))
    phone = UgPhoneField(label="Business phone", help_text="Shown on your public profile.")
    email = forms.EmailField(label="Business email", required=False)


class VerificationForm(StyledForm, forms.Form):
    note = forms.CharField(label="How can we verify your business?", min_length=20, max_length=1000, widget=forms.Textarea(attrs={"rows": 3}),
                           help_text="E.g. your URSB registration number or trading licence, and a time we can visit or call. "
                                     "Don't paste ID numbers here; we'll ask for documents securely.")


class DealForm(StyledForm, forms.Form):
    title = forms.CharField(label="Deal title", min_length=4, max_length=90, widget=forms.TextInput(attrs={"placeholder": "e.g. Rolex + juice combo"}))
    discount_label = forms.CharField(label="Headline", min_length=2, max_length=30, help_text="Short: “20% off”, “Free gift”.")
    description = forms.CharField(min_length=10, max_length=1500, widget=forms.Textarea(attrs={"rows": 3}))
    original_price_ugx = UGXField(label="Normal price (UGX)", required=False)
    deal_price_ugx = UGXField(label="Deal price (UGX)", required=False)
    terms = forms.CharField(required=False, max_length=800, widget=forms.Textarea(attrs={"rows": 2, "placeholder": "e.g. Valid Mon–Thu, one per student."}))
    campus = forms.ModelChoiceField(queryset=Campus.objects.filter(is_active=True).select_related("institution"), required=False,
                                    empty_label="All campuses", label="Which campus?")
    ends_at = EndOfDayField(label="Ends on")
    redemption = forms.ChoiceField(choices=Deal.Redemption.choices, label="How students redeem")
    shared_code = forms.CharField(required=False, max_length=24, label="Your promo code", help_text="Only for “Your own promo code”.")
    max_claims = forms.IntegerField(required=False, min_value=1, max_value=100_000, label="Maximum claims", help_text="Leave empty for unlimited.")

    def clean_shared_code(self):
        return self.cleaned_data["shared_code"].strip().upper()

    def clean(self):
        d = super().clean()
        if d.get("redemption") == Deal.Redemption.SHARED_CODE and not d.get("shared_code"):
            self.add_error("shared_code", "Enter the code students should use.")
        o, p = d.get("original_price_ugx"), d.get("deal_price_ugx")
        if o is not None and p is not None and p >= o:
            self.add_error("deal_price_ugx", "Deal price should be lower than the normal price.")
        return d


class RedeemForm(StyledForm, forms.Form):
    code = forms.CharField(max_length=40, label="Student code", widget=forms.TextInput(attrs={"placeholder": "CH-XXXXXXXX", "autocomplete": "off", "class": "input font-mono uppercase"}))
