from django import forms
from django.contrib.auth import password_validation

from core.forms import StyledForm, UgPhoneField, campus_field


class RegisterForm(StyledForm, forms.Form):
    full_name = forms.CharField(label="Full name", min_length=2, max_length=80, widget=forms.TextInput(attrs={"autocomplete": "name"}))
    email = forms.EmailField(label="Email", max_length=160, widget=forms.EmailInput(attrs={"autocomplete": "email"}),
                             help_text="Your university email works best for student verification.")
    phone = UgPhoneField(label="Phone", required=False, help_text="Ugandan number, e.g. 0772 123 456. Never shown publicly.")
    password = forms.CharField(label="Password", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
                               help_text="At least 8 characters. Avoid common passwords.")
    agree = forms.BooleanField(error_messages={"required": "You must accept the Terms and Privacy Policy."})

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def clean(self):
        data = super().clean()
        if data.get("password"):
            from accounts.models import User

            try:
                password_validation.validate_password(data["password"], User(email=data.get("email", ""), full_name=data.get("full_name", "")))
            except forms.ValidationError as e:
                self.add_error("password", e)
        return data


class LoginForm(StyledForm, forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={"autocomplete": "email"}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))


class ForgotForm(StyledForm, forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={"autocomplete": "email"}))


class ResetForm(StyledForm, forms.Form):
    password = forms.CharField(label="New password", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
                               help_text="At least 8 characters. Avoid common passwords.")

    def __init__(self, user, *a, **kw):
        self.user = user
        super().__init__(*a, **kw)

    def clean_password(self):
        pw = self.cleaned_data["password"]
        password_validation.validate_password(pw, self.user)
        return pw


class OnboardingForm(StyledForm, forms.Form):
    campus = campus_field(label="Your campus", help_text="We'll show listings, gigs and deals near this campus first. You can change it later.")
    phone = UgPhoneField(label="Phone", required=False, help_text="Used for account security and future mobile-money payments. Never shown publicly.")


class ProfileForm(StyledForm, forms.Form):
    full_name = forms.CharField(label="Full name", min_length=2, max_length=80)
    campus = campus_field(label="Campus")
    phone = UgPhoneField(label="Phone", required=False, help_text="Private. Never shown on your profile.")
    bio = forms.CharField(label="Bio", required=False, max_length=400, widget=forms.Textarea(attrs={"rows": 3}),
                          help_text="What you study, what you sell or offer.")


class DeleteAccountForm(StyledForm, forms.Form):
    password = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))
    confirm = forms.CharField(label='Type "DELETE" to confirm')

    def clean_confirm(self):
        if self.cleaned_data["confirm"] != "DELETE":
            raise forms.ValidationError('Type DELETE in capitals to confirm.')
        return "DELETE"
