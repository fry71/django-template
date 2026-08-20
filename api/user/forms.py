# api/user/forms.py
from __future__ import annotations

from django import forms


class MessageForm(forms.Form):
    """Form for submitting a chat message."""

    content = forms.CharField(
        label="Message",
        max_length=4000,
        min_length=1,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Type a message…",
                "autofocus": True,
            },
        ),
    )
