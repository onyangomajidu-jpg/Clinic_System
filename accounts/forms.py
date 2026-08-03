from django import forms
from django.contrib.auth.forms import AuthenticationForm


class StaffLoginForm(AuthenticationForm):
    """
    Django's built-in AuthenticationForm, with the field widgets styled for
    the login template and a plainer error message (NFR-7: plain,
    non-technical language for staff with varying computer literacy).

    Login itself is unchanged: this still validates against Django's
    hashed-password auth backend and still respects User.is_active, so an
    offboarded staff member (see accounts.signals) cannot log in.
    """

    username = forms.CharField(
        widget=forms.TextInput(
            attrs={"autofocus": True, "class": "input", "placeholder": "Username", "autocapitalize": "none"}
        )
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "input", "placeholder": "Password"})
    )

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "That username or password wasn't right. Please try again.",
        "inactive": "This account has been deactivated. Please see your clinic administrator.",
    }
