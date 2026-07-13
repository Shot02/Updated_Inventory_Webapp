# select_branch/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from branches.models import Branch


@login_required
def select_branch(request):
    """View for users to select their branch"""
    # If user already has a branch and it's active, redirect to home
    if request.user.branch and request.user.branch.is_active:
        if request.user.role == 'admin' or request.user.is_superuser:
            return redirect('admin_dashboard')
        else:
            return redirect('home')
    
    # Get all active branches
    branches = Branch.objects.filter(is_active=True).order_by('name')
    
    if not branches.exists():
        messages.warning(request, 'No active branches available. Please contact the administrator.')
        return redirect('home')
    
    if request.method == 'POST':
        branch_id = request.POST.get('branch_id')
        if branch_id:
            try:
                branch = Branch.objects.get(id=branch_id, is_active=True)
                request.user.branch = branch
                request.user.save()
                messages.success(request, f'Welcome to {branch.name}!')
                
                if request.user.role == 'admin' or request.user.is_superuser:
                    return redirect('admin_dashboard')
                else:
                    return redirect('home')
            except Branch.DoesNotExist:
                messages.error(request, 'Invalid branch selected.')
        else:
            messages.error(request, 'Please select a branch.')
    
    context = {
        'branches': branches,
    }
    return render(request, 'select_branch/select_branch.html', context)