from django import forms
from .models import ChapterSummary, Category


from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        required=True, help_text="Required. Enter a valid email address."
    )

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already registered.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name"]


class ChapterSummaryForm(forms.ModelForm):
    class Meta:
        model = ChapterSummary
        fields = [
            "chapter_title",
            "main_idea",
            "key_lessons",
            "concepts",
            "examples",
            "actions",
            "personal_insight",
            "category",
        ]
        widgets = {
            "category": forms.Select(attrs={"class": "form-control"}),
        }
