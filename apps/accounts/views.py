from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from apps.people.models import Person

from .forms import ChangeRoleForm, MakeAdministratorForm, PersonSearchForm
from .mixins import SuperAdminRequiredMixin
from .models import User
from .services import AdministratorService, AlreadyAdministratorError, NotSuperAdminError


class AdministratorListView(SuperAdminRequiredMixin, ListView):
    model = User
    template_name = 'accounts/list.html'
    context_object_name = 'administrators'
    paginate_by = 25

    def get_queryset(self):
        return User.objects.select_related('person').order_by('-created_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['role_form'] = ChangeRoleForm()
        return ctx


class FindPersonToPromoteView(SuperAdminRequiredMixin, ListView):
    """Step 1 of the workflow: 'Open Person Profile'. A lightweight
    search rather than a full People directory (that's a later phase) —
    just enough to locate the right person to promote."""

    template_name = 'accounts/find_person.html'
    context_object_name = 'people'
    paginate_by = 10

    def get_queryset(self):
        q = self.request.GET.get('q', '').strip()
        if not q:
            return Person.objects.none()
        return Person.objects.filter(
            Q(first_name__icontains=q) | Q(last_name__icontains=q)
            | Q(phone_number__icontains=q) | Q(email_address__icontains=q)
            | Q(person_id__iexact=q)
        ).select_related('administrator_account')[:25]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['search_form'] = PersonSearchForm(initial={'q': self.request.GET.get('q', '')})
        ctx['query'] = self.request.GET.get('q', '')
        return ctx


def make_administrator(request, person_id):
    if not getattr(request.user, 'is_super_admin', False):
        messages.error(request, "Only the Super Administrator can create administrators.")
        return redirect('dashboard:home')

    person = get_object_or_404(Person, person_id=person_id)

    if hasattr(person, 'administrator_account'):
        messages.info(request, f"{person.full_name} is already an administrator.")
        return redirect('accounts:list')

    if request.method == 'POST':
        form = MakeAdministratorForm(request.POST)
        if form.is_valid():
            try:
                credentials = AdministratorService.create_administrator(
                    person=person, role=form.cleaned_data['role'], requested_by=request.user,
                )
            except (AlreadyAdministratorError, NotSuperAdminError) as e:
                messages.error(request, str(e))
                return redirect('accounts:list')

            request.session['new_admin_credentials'] = {
                'username': credentials.username,
                'password': credentials.temporary_password,
                'full_name': person.full_name,
                'email_sent': credentials.email_sent,
            }
            return redirect('accounts:credentials')
    else:
        form = MakeAdministratorForm()

    return render(request, 'accounts/make_administrator.html', {'person': person, 'form': form})


def credentials_reveal(request):
    """One-time reveal: the temporary password only ever exists in the
    session for a single render, then it's gone — mirroring how it can
    never be retrieved from the database again after this point."""
    data = request.session.pop('new_admin_credentials', None)
    if not data:
        messages.info(request, "No new credentials to show. This page can only be viewed once.")
        return redirect('accounts:list')
    return render(request, 'accounts/credentials.html', {'data': data})


@require_POST
def toggle_active(request, user_id):
    if not getattr(request.user, 'is_super_admin', False):
        messages.error(request, "Only the Super Administrator can do that.")
        return redirect('accounts:list')

    user = get_object_or_404(User, pk=user_id)
    if user == request.user:
        messages.error(request, "You can't deactivate your own account.")
        return redirect('accounts:list')

    AdministratorService.set_active(user=user, is_active=not user.is_active_administrator, requested_by=request.user)
    messages.success(request, f"{user.username} {'reactivated' if user.is_active_administrator else 'deactivated'}.")
    return redirect('accounts:list')


@require_POST
def reset_password(request, user_id):
    if not getattr(request.user, 'is_super_admin', False):
        messages.error(request, "Only the Super Administrator can do that.")
        return redirect('accounts:list')

    user = get_object_or_404(User, pk=user_id)
    credentials = AdministratorService.reset_password(user=user, requested_by=request.user)
    request.session['new_admin_credentials'] = {
        'username': credentials.username,
        'password': credentials.temporary_password,
        'full_name': user.get_full_name() or user.username,
        'email_sent': credentials.email_sent,
        'is_reset': True,
    }
    return redirect('accounts:credentials')


@require_POST
def change_role(request, user_id):
    if not getattr(request.user, 'is_super_admin', False):
        messages.error(request, "Only the Super Administrator can do that.")
        return redirect('accounts:list')

    user = get_object_or_404(User, pk=user_id)
    form = ChangeRoleForm(request.POST)
    if form.is_valid():
        AdministratorService.change_role(user=user, role=form.cleaned_data['role'], requested_by=request.user)
        messages.success(request, f"{user.username}'s role updated.")
    return redirect('accounts:list')
