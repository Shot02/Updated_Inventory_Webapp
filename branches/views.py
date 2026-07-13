from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import Branch
from inventoryApp.utils import safe_decimal
from products.models import Product
from sales.models import Sale, Payment
from inventoryApp.models import User
from django.db.models import Sum, Count, Q  

@login_required
def branch_list(request):
    """List all branches with statistics (admin only)"""
    if not (request.user.is_superuser or request.user.role == 'admin'):
        messages.error(request, 'Only admins can manage branches')
        return redirect('home')
    
    branches = Branch.objects.all().order_by('name')
    
    branches_with_stats = []
    for branch in branches:
        products = Product.objects.filter(branch=branch)
        sales = Sale.objects.filter(branch=branch)
        payments = Payment.objects.filter(sale__branch=branch)
        
        cash_total = safe_decimal(payments.filter(payment_method='cash').aggregate(total=Sum('amount'))['total'])
        transfer_total = safe_decimal(payments.filter(payment_method='transfer').aggregate(total=Sum('amount'))['total'])
        card_total = safe_decimal(payments.filter(payment_method='card').aggregate(total=Sum('amount'))['total'])
        total_revenue = safe_decimal(payments.aggregate(total=Sum('amount'))['total'])
        staff_count = User.objects.filter(branch=branch, is_active=True).count()
        
        branches_with_stats.append({
            'branch': branch,
            'product_count': products.count(),
            'staff_count': staff_count,
            'cash_total': cash_total,
            'transfer_total': transfer_total,
            'card_total': card_total,
            'total_revenue': total_revenue,
            'sales_count': sales.count(),
        })
    
    search_query = request.GET.get('search', '')
    if search_query:
        branches = branches.filter(
            Q(name__icontains=search_query) |
            Q(code__icontains=search_query) |
            Q(manager__icontains=search_query)
        )
        branches_with_stats = [
            item for item in branches_with_stats 
            if item['branch'] in branches
        ]
    
    current_branch_id = request.session.get('current_branch_id')
    current_branch = None
    if current_branch_id:
        try:
            current_branch = Branch.objects.get(id=current_branch_id)
        except Branch.DoesNotExist:
            current_branch = None
    
    context = {
        'branches_with_stats': branches_with_stats,
        'search_query': search_query,
        'current_branch': current_branch,
        'branch_switched': request.session.get('branch_switched', False)
    }
    return render(request, 'branches/branch_list.html', context)

@login_required
def add_branch(request):
    if not (request.user.is_superuser or request.user.role == 'admin'):
        messages.error(request, 'Only admins can add branches')
        return redirect('home')
    
    if request.method == 'POST':
        try:
            name = request.POST.get('name', '').strip()
            code = request.POST.get('code', '').strip().upper()
            address = request.POST.get('address', '').strip()
            phone = request.POST.get('phone', '').strip()
            email = request.POST.get('email', '').strip()
            manager = request.POST.get('manager', '').strip()
            is_active = request.POST.get('is_active', '1') == '1'
            
            if not name:
                messages.error(request, 'Branch name is required')
                return redirect('add_branch')
            
            if not code:
                messages.error(request, 'Branch code is required')
                return redirect('add_branch')
            
            if Branch.objects.filter(code=code).exists():
                messages.error(request, f'Branch code "{code}" already exists')
                return redirect('add_branch')
            
            branch = Branch.objects.create(
                name=name,
                code=code,
                address=address or None,
                phone=phone or None,
                email=email or None,
                manager=manager or None,
                is_active=is_active
            )
            
            messages.success(request, f'Branch "{branch.name}" created successfully!')
            return redirect('branch_list')
            
        except Exception as e:
            messages.error(request, f'Error creating branch: {str(e)}')
            return redirect('add_branch')
    
    return render(request, 'branches/branch_form.html', {'action': 'Add'})

@login_required
def edit_branch(request, pk):
    if not (request.user.is_superuser or request.user.role == 'admin'):
        messages.error(request, 'Only admins can edit branches')
        return redirect('home')
    
    branch = get_object_or_404(Branch, id=pk)
    
    if request.method == 'POST':
        try:
            branch.name = request.POST.get('name', '').strip()
            branch.code = request.POST.get('code', '').strip().upper()
            branch.address = request.POST.get('address', '').strip()
            branch.phone = request.POST.get('phone', '').strip()
            branch.email = request.POST.get('email', '').strip()
            branch.manager = request.POST.get('manager', '').strip()
            branch.is_active = request.POST.get('is_active', '1') == '1'
            
            if not branch.name:
                messages.error(request, 'Branch name is required')
                return redirect('edit_branch', pk=pk)
            
            if not branch.code:
                messages.error(request, 'Branch code is required')
                return redirect('edit_branch', pk=pk)
            
            if Branch.objects.filter(code=branch.code).exclude(id=branch.id).exists():
                messages.error(request, f'Branch code "{branch.code}" already exists')
                return redirect('edit_branch', pk=pk)
            
            branch.save()
            
            messages.success(request, f'Branch "{branch.name}" updated successfully!')
            return redirect('branch_list')
            
        except Exception as e:
            messages.error(request, f'Error updating branch: {str(e)}')
    
    context = {
        'branch': branch,
        'action': 'Edit',
    }
    return render(request, 'branches/branch_form.html', context)

@login_required
def delete_branch(request, pk):
    if not (request.user.is_superuser or request.user.role == 'admin'):
        return JsonResponse({'success': False, 'error': 'Only admins can delete branches'})
    
    if request.method == 'POST':
        try:
            branch = get_object_or_404(Branch, id=pk)
            
            if branch.users.filter(is_active=True).exists():
                return JsonResponse({
                    'success': False, 
                    'error': f'Cannot delete branch "{branch.name}" because it has active staff members assigned.'
                })
            
            branch.delete()
            return JsonResponse({'success': True})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def switch_branch(request, branch_id):
    """Switch to a specific branch (admin only)"""
    if not request.user.is_superuser and request.user.role != 'admin':
        messages.error(request, 'Only admins can switch branches')
        return redirect('home')
    
    try:
        branch = Branch.objects.get(id=branch_id, is_active=True)
        request.session['current_branch_id'] = branch_id
        request.session['branch_switched'] = True
        messages.success(request, f'Switched to {branch.name}')
    except Branch.DoesNotExist:
        messages.error(request, 'Branch not found')
        request.session['current_branch_id'] = None
        request.session['branch_switched'] = False
    
    return redirect('admin_dashboard')

@login_required
def clear_branch_selection(request):
    """Clear branch selection and show all branches (admin only)"""
    if not request.user.is_superuser and request.user.role != 'admin':
        messages.error(request, 'Only admins can clear branch selection')
        return redirect('home')
    
    request.session['current_branch_id'] = None
    request.session['branch_switched'] = False
    messages.success(request, 'Now viewing all branches')
    return redirect('admin_dashboard')