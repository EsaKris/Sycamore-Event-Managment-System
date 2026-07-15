from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from apps.core.models import AuditLog

from .forms import DepartmentForm
from .models import Department


class DepartmentListView(LoginRequiredMixin, ListView):
    login_url = 'dashboard:login'
    model = Department
    template_name = 'departments/list.html'
    context_object_name = 'departments'

    def get_queryset(self):
        from django.db.models import Count, Q
        return Department.objects.annotate(
            worker_count=Count('registrations', filter=Q(registrations__category='worker')),
        ).order_by('-is_active', 'name')


@login_required(login_url='dashboard:login')
def department_form(request, pk=None):
    department = get_object_or_404(Department, pk=pk) if pk else None
    if request.method == 'POST':
        form = DepartmentForm(request.POST, instance=department)
        if form.is_valid():
            is_new = department is None
            department = form.save()
            AuditLog.objects.create(
                administrator=request.user,
                action=f"{'Created' if is_new else 'Updated'} department '{department.name}'",
                model_name='Department', object_id=department.id,
                ip_address=getattr(request, 'client_ip', None),
            )
            messages.success(request, f"Department '{department.name}' saved.")
            return redirect('departments:list')
    else:
        form = DepartmentForm(instance=department)
    return render(request, 'departments/form.html', {'form': form, 'department': department})


@login_required(login_url='dashboard:login')
@require_POST
def department_toggle_active(request, pk):
    department = get_object_or_404(Department, pk=pk)
    department.is_active = not department.is_active
    department.save(update_fields=['is_active'])
    AuditLog.objects.create(
        administrator=request.user,
        action=f"{'Activated' if department.is_active else 'Archived'} department '{department.name}'",
        model_name='Department', object_id=department.id,
        ip_address=getattr(request, 'client_ip', None),
    )
    messages.success(request, f"'{department.name}' {'activated' if department.is_active else 'archived'}.")
    return redirect('departments:list')
