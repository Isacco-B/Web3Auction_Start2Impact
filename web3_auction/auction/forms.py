from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from .models import Auction
from django.utils import timezone
import json


User = get_user_model()


class AuctionForm(forms.ModelForm):
    class Meta:
        model = Auction
        fields = (
            "title",
            "description",
            "image",
            "current_price",
            "end_date",
        )
        labels = {"current_price": "Initial price"}
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Your auction title"}),
            "description": forms.Textarea(attrs={"placeholder": "Your auction description"}),
            "current_price": forms.TextInput(attrs={"placeholder": "Initial price"}),
            "end_date": forms.TextInput(attrs={"type": "datetime-local", "required": True}),
        }

    def clean_end_date(self):
        current_datetime = timezone.now()
        end_date = self.cleaned_data.get("end_date")

        if end_date <= current_datetime:
            raise ValidationError("Error, invalid date, please enter a valid date!")

        return end_date


class AuctionUpdateForm(forms.ModelForm):
    class Meta:
        model = Auction
        fields = (
            "title",
            "description",
            "end_date",
        )
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Your auction title"}),
            "description": forms.Textarea(attrs={"placeholder": "Your auction description"}),
            "end_date": forms.TextInput(attrs={"type": "datetime-local", "required": True}),
        }

    def clean_end_date(self):
        current_datetime = timezone.now()
        end_date = self.cleaned_data.get("end_date")

        if end_date <= current_datetime:
            raise ValidationError("Error, invalid date, please enter a valid date!")

        return end_date


class AuctionUpdateStatusForm(AuctionForm):
    AUCTION_STATUS = (
        ("Active", "Active"),
        ("Inactive", "Inactive"),
    )
    status = forms.ChoiceField(choices=AUCTION_STATUS)


class BidForm(forms.Form):
    def __init__(self, *args, request=None, pk=None, **kwargs):
        self.request = request
        self.pk = pk
        super(BidForm, self).__init__(*args, **kwargs)

    amount = forms.IntegerField(
        min_value=0, required=True, widget=forms.TextInput(attrs={"placeholder": "make an offer"})
    )

    def clean_amount(self):
        auction_id = self.pk
        auction = get_object_or_404(Auction, pk=auction_id)
        amount = self.cleaned_data.get("amount")

        cache_key = f"auction_{auction_id}"
        existing_bid_data = cache.get(cache_key)

        if existing_bid_data:
            bid_data = json.loads(existing_bid_data)
            last_bid = bid_data[-1]
            print(last_bid)
            if amount <= last_bid["amount"]:
                raise ValidationError("Error, you have to offer more than the last offer")

        if auction.owner == self.request.user:
            raise ValidationError("Error, you cannot bid on auctions you own")

        if auction.status == "Close":
            raise ValidationError("Error, the auction has ended")

        if amount <= auction.current_price:
            raise ValidationError("Error, you have to offer more than the start price")

        return amount
