from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Sum

# Core imports
from inventoryApp.models import User, UserNotification
from inventoryApp.utils import safe_decimal

# Branch imports
from branches.models import Branch

# Customer imports (self)
from .models import Customer

@login_required
def customer_list(request):
    """List all customers - filtered by branch"""
    current_branch = None
    if request.user.is_superuser or request.user.role == 'admin':
        branch_id = request.session.get('current_branch_id')
        if branch_id:
            try:
                current_branch = Branch.objects.get(id=branch_id)
            except Branch.DoesNotExist:
                current_branch = None
    else:
        current_branch = request.user.branch
    
    customers = Customer.objects.all()
    
    if current_branch:
        customers = customers.filter(branch=current_branch)
    elif not (request.user.is_superuser or request.user.role == 'admin'):
        customers = customers.none()
    
    customers = customers.order_by('-created_at')
    
    total_customers = customers.count()
    vip_count = customers.filter(customer_type='vip').count()
    wholesale_count = customers.filter(customer_type='wholesale').count()
    total_points = customers.aggregate(total=Sum('loyalty_points'))['total'] or 0
    
    search_query = request.GET.get('search', '')
    if search_query:
        customers = customers.filter(
            Q(name__icontains=search_query) |
            Q(phone__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    context = {
        'customers': customers,
        'total_customers': total_customers,
        'vip_count': vip_count,
        'wholesale_count': wholesale_count,
        'total_points': total_points,
        'search_query': search_query,
        'current_branch': current_branch,
        'viewing_all_branches': current_branch is None and (request.user.is_superuser or request.user.role == 'admin')
    }
    return render(request, 'customers/customer_list.html', context)

@login_required
def add_customer(request):
    if request.method == 'POST':
        try:
            name = request.POST.get('name', '').strip()
            phone = request.POST.get('phone', '').strip()
            email = request.POST.get('email', '').strip()
            address = request.POST.get('address', '').strip()
            customer_type = request.POST.get('customer_type', 'regular')
            notes = request.POST.get('notes', '').strip()
            is_active = request.POST.get('is_active', '1') == '1'
            
            if not name:
                messages.error(request, 'Customer name is required')
                return render(request, 'customers/customer_form.html', {'action': 'Add'})
            
            if not phone:
                messages.error(request, 'Phone number is required')
                return render(request, 'customers/customer_form.html', {'action': 'Add'})
            
            if Customer.objects.filter(phone=phone).exists():
                messages.error(request, 'A customer with this phone number already exists')
                return render(request, 'customers/customer_form.html', {'action': 'Add'})
            
            current_branch = request.user.branch
            if request.user.is_superuser or request.user.role == 'admin':
                branch_id = request.session.get('current_branch_id')
                if branch_id:
                    try:
                        current_branch = Branch.objects.get(id=branch_id)
                    except Branch.DoesNotExist:
                        current_branch = None
            
            customer = Customer.objects.create(
                name=name,
                phone=phone,
                email=email if email else None,
                address=address,
                customer_type=customer_type,
                notes=notes,
                is_active=is_active,
                branch=current_branch
            )
            
            messages.success(request, f'Customer "{customer.name}" added successfully!')
            return redirect('customer_list')
            
        except Exception as e:
            messages.error(request, f'Error adding customer: {str(e)}')
    
    return render(request, 'customers/customer_form.html', {'action': 'Add'})

@login_required
def edit_customer(request, pk):
    customer = get_object_or_404(Customer, id=pk)
    
    if request.method == 'POST':
        try:
            customer.name = request.POST.get('name', '').strip()
            customer.phone = request.POST.get('phone', '').strip()
            customer.email = request.POST.get('email', '').strip()
            customer.address = request.POST.get('address', '').strip()
            customer.customer_type = request.POST.get('customer_type', 'regular')
            customer.notes = request.POST.get('notes', '').strip()
            customer.is_active = request.POST.get('is_active', '1') == '1'
            
            if not customer.name:
                messages.error(request, 'Customer name is required')
                return render(request, 'customers/customer_form.html', {'customer': customer, 'action': 'Edit'})
            
            if not customer.phone:
                messages.error(request, 'Phone number is required')
                return render(request, 'customers/customer_form.html', {'customer': customer, 'action': 'Edit'})
            
            if Customer.objects.filter(phone=customer.phone).exclude(id=customer.id).exists():
                messages.error(request, 'A customer with this phone number already exists')
                return render(request, 'customers/customer_form.html', {'customer': customer, 'action': 'Edit'})
            
            customer.save()
            
            messages.success(request, f'Customer "{customer.name}" updated successfully!')
            return redirect('customer_list')
            
        except Exception as e:
            messages.error(request, f'Error updating customer: {str(e)}')
    
    return render(request, 'customers/customer_form.html', {'customer': customer, 'action': 'Edit'})

@login_required
def delete_customer(request, pk):
    if request.method == 'POST':
        customer = get_object_or_404(Customer, id=pk)
        
        if not (request.user.is_superuser or request.user.role == 'admin'):
            if request.user.branch and customer.sale_set.filter(branch=request.user.branch).exists():
                return JsonResponse({'success': False, 'error': 'This customer has sales in your branch.'})
        
        customer.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid method'})