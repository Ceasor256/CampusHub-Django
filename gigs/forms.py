from django import forms

from core.forms import EndOfDayField, StyledForm, UGXField, campus_field
from core.models import Category
from core.utils import looks_like_academic_dishonesty

from .models import Gig


class GigForm(StyledForm, forms.Form):
    title = forms.CharField(label="What do you need done?", min_length=6, max_length=90, help_text="E.g. “Design a poster for our club event”.")
    category = forms.ModelChoiceField(queryset=Category.objects.none(), empty_label="Choose a category", error_messages={"required": "Choose a category."})
    description = forms.CharField(label="Details", min_length=20, max_length=3000, widget=forms.Textarea(attrs={"rows": 6}),
                                  help_text="What exactly is needed, what you'll provide, and how you'll judge it's done.")
    budget_ugx = UGXField(label="Budget (UGX)", min_value=1_000, max_value=50_000_000, help_text="Minimum UGX 1,000. Applicants can propose a price.")
    deadline = EndOfDayField(required=False, label="Deadline")
    mode = forms.ChoiceField(choices=Gig.Mode.choices, label="Where", initial="in_person")
    campus = campus_field(label="Campus")
    location_note = forms.CharField(required=False, max_length=140, label="Location details",
                                    widget=forms.TextInput(attrs={"placeholder": "e.g. Mitchell Hall, room 12"}))

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["category"].queryset = Category.objects.filter(module="gigs", is_active=True)

    def clean(self):
        d = super().clean()
        if looks_like_academic_dishonesty(f"{d.get('title', '')} {d.get('description', '')}"):
            self.add_error("description", "CampusHub doesn't allow gigs to complete graded work or exams for someone else. "
                                          "Tutoring, proofreading guidance and study help are welcome.")
        return d


class ApplicationForm(StyledForm, forms.Form):
    message = forms.CharField(label="Why you?", min_length=10, max_length=1000, widget=forms.Textarea(attrs={"rows": 4}),
                              help_text="Share relevant experience and when you can do it.")
    proposed_ugx = UGXField(label="Your price (UGX)", min_value=1_000, max_value=50_000_000)


class ReviewForm(forms.Form):
    rating = forms.TypedChoiceField(coerce=int, choices=[(i, i) for i in range(1, 6)], widget=forms.RadioSelect, error_messages={"required": "Choose a rating."})
    comment = forms.CharField(required=False, max_length=500)
