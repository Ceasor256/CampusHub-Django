from datetime import datetime, time

from django import forms
from django.utils import timezone

from core.models import Campus, Report
from core.utils import normalize_ug_phone, parse_ugx


class StyledForm:
    """Adds the design-system class to every widget."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            w = f.widget
            if isinstance(w, (forms.CheckboxInput, forms.RadioSelect, forms.ClearableFileInput)):
                continue
            w.attrs.setdefault("class", "input")


class UGXField(forms.CharField):
    """Accepts '450000', '450,000' or 'UGX 450000'. Cleans to an int (whole shillings)."""

    def __init__(self, *, min_value=0, max_value=1_000_000_000, **kw):
        self.min_value, self.max_value = min_value, max_value
        kw.setdefault("widget", forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "off"}))
        super().__init__(**kw)

    def clean(self, value):
        value = super().clean(value)
        if value in (None, ""):
            return None
        n = parse_ugx(value)
        if n is None:
            raise forms.ValidationError("Enter an amount in UGX, digits only.")
        if n < self.min_value:
            raise forms.ValidationError(f"Must be at least UGX {self.min_value:,}.")
        if n > self.max_value:
            raise forms.ValidationError("That amount is too large.")
        return n


class UgPhoneField(forms.CharField):
    def __init__(self, **kw):
        kw.setdefault("widget", forms.TextInput(attrs={"type": "tel", "inputmode": "tel", "placeholder": "07XX XXX XXX", "autocomplete": "tel"}))
        kw.setdefault("max_length", 20)
        super().__init__(**kw)

    def clean(self, value):
        value = super().clean(value)
        if not value:
            return ""
        n = normalize_ug_phone(value)
        if not n:
            raise forms.ValidationError("Enter a valid Ugandan number, e.g. 0772 123 456 or +256 772 123 456.")
        return n


class EndOfDayField(forms.DateField):
    """A date input that cleans to 23:59 Kampala time on that day, and must be in the future."""

    def __init__(self, **kw):
        kw.setdefault("widget", forms.DateInput(attrs={"type": "date"}))
        super().__init__(**kw)

    def clean(self, value):
        d = super().clean(value)
        if d is None:
            return None
        dt = timezone.make_aware(datetime.combine(d, time(23, 59)))
        if dt <= timezone.now():
            raise forms.ValidationError("Choose a date in the future.")
        return dt


def campus_field(**kw):
    return forms.ModelChoiceField(
        queryset=Campus.objects.filter(is_active=True, institution__is_active=True).select_related("institution"),
        empty_label="Choose your campus",
        error_messages={"required": "Choose a campus.", "invalid_choice": "Choose an available campus."},
        **kw,
    )


class ReportForm(StyledForm, forms.Form):
    target_type = forms.ChoiceField(choices=Report.Target.choices, widget=forms.HiddenInput)
    target_id = forms.UUIDField(widget=forms.HiddenInput)
    reason = forms.ChoiceField(choices=[("", "Choose a reason")] + list(Report.Reason.choices), label="What's wrong?")
    details = forms.CharField(required=False, max_length=1000, widget=forms.Textarea(attrs={"rows": 3}), label="Details")


class MessageForm(StyledForm, forms.Form):
    body = forms.CharField(max_length=2000, strip=True, widget=forms.Textarea(attrs={"rows": 3}), label="Message",
                           error_messages={"required": "Write a message first."})
