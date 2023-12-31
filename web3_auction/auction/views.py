from django.urls import reverse_lazy
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from django.views.generic import DetailView, ListView, CreateView, DeleteView, UpdateView
from .models import Auction, Bid
from .forms import AuctionForm, AuctionUpdateForm, AuctionUpdateStatusForm, BidForm
from .mixins import IsAuctionOwner
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.cache import cache
from django.utils import timezone, dateformat
import json


User = get_user_model()


# -------Auction View-------


class AuctionListView(LoginRequiredMixin, ListView):
    model = Auction
    context_object_name = "auctions"
    template_name = "../templates/auction/auction_list.html"

    def get_queryset(self):
        queryset = super().get_queryset()

        status_filter = self.request.GET.get("status_filter")
        if status_filter == "active":
            queryset = queryset.filter(status="Active")
        elif status_filter == "inactive":
            queryset = queryset.filter(status="Inactive")
        elif status_filter == "close":
            queryset = queryset.filter(status="Closed")

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        for auction in context["auctions"]:
            cache_key = f"auction_{auction.id}"
            bid_list = cache.get(cache_key)
            if bid_list:
                bids = json.loads(bid_list)
                highest_bid = bids[-1]
                auction.highest_bid = highest_bid

        return context


auction_list_view = AuctionListView.as_view()


class AuctionDetailView(LoginRequiredMixin, DetailView):
    context_object_name = "auction"
    template_name = "../templates/auction/auction_detail.html"

    def get_queryset(self):
        return Auction.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        auction_id = self.kwargs["pk"]
        cache_key = f"auction_{auction_id}"
        bid_list = cache.get(cache_key)
        context["bid_form"] = BidForm()
        if bid_list:
            context["bid_list"] = json.loads(bid_list)
        return context


auction_detail_view = AuctionDetailView.as_view()


class AuctionCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    form_class = AuctionForm
    template_name = "../templates/auction/auction_create.html"
    success_message = "Auction successfully created"

    def form_valid(self, form):
        user = User.objects.get(id=self.request.user.id)
        auction = form.save(commit=False)
        auction.owner = user
        auction.save()
        return super(AuctionCreateView, self).form_valid(form)

    def get_success_url(self):
        return reverse_lazy("auctions:list")


auction_create_view = AuctionCreateView.as_view()


class AuctionUpdateView(LoginRequiredMixin, IsAuctionOwner, SuccessMessageMixin, UpdateView):
    model = Auction
    template_name = "../templates/auction/auction_update.html"
    success_message = "Auction successfully updated"

    def get_form_class(self):
        if self.object.status == "Inactive":
            return AuctionUpdateStatusForm
        else:
            return AuctionUpdateForm

    def form_valid(self, form):
        if self.object.status == "Closed":
            messages.error(self.request, "You cannot update this auction.")
            return redirect("auctions:list")

        if self.get_form_class() == AuctionUpdateStatusForm:
            auction = form.save(commit=False)
            status = form.cleaned_data["status"]
            auction.status = status
            auction.save()
        return super().form_valid(form)

    def get_queryset(self):
        return Auction.objects.all()

    def get_success_url(self):
        return reverse_lazy("auctions:list")


auction_update_view = AuctionUpdateView.as_view()


class AuctionDeleteView(LoginRequiredMixin, IsAuctionOwner, SuccessMessageMixin, DeleteView):
    context_object_name = "auction"
    template_name = "../templates/auction/auction_delete.html"
    success_message = "Auction successfully deleted"

    def get_queryset(self):
        return Auction.objects.all()

    def get_success_url(self):
        return reverse_lazy("auctions:list")


auction_delete_view = AuctionDeleteView.as_view()


# -------Bid View-------


@require_POST
@login_required
def save_form_data_to_cache(request, pk):
    form = BidForm(request.POST, request=request, pk=pk)

    if form.is_valid():
        amount = form.cleaned_data["amount"]
        auction_id = pk
        user_id = request.user.pk
        bidder_username = request.user.profile.username

        cache_key = f"auction_{auction_id}"
        existing_bid_data = cache.get(cache_key)

        if existing_bid_data:
            existing_bid_data = json.loads(existing_bid_data)
            existing_bid_data.append(
                {
                    "amount": amount,
                    "user_id": user_id,
                    "bidder_username": bidder_username,
                    "auction_id": auction_id,
                    "bid_date": str(dateformat.format(timezone.now(), "Y-m-d H:i:s")),
                }
            )
            cache.set(cache_key, json.dumps(existing_bid_data), timeout=None)
        else:
            bid_data = [
                {
                    "amount": amount,
                    "user_id": user_id,
                    "bidder_username": bidder_username,
                    "auction_id": auction_id,
                    "bid_date": str(dateformat.format(timezone.now(), "Y-m-d H:i:s")),
                }
            ]
            cache.set(cache_key, json.dumps(bid_data), timeout=None)

        messages.success(request, "offer sent successfully")
        return redirect("auctions:detail", pk)
    else:
        error_message = form.errors.get("amount", None)
        if error_message:
            messages.error(request, error_message)
        else:
            messages.error(request, "something went wrong, try again")
        return redirect("auctions:detail", pk)
