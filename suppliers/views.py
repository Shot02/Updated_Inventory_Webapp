from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Sum
from decimal import Decimal

# inventoryApp imports
from inventoryApp.models import User, UserNotification
from inventoryApp.utils import safe_decimal

# Branch imports
from branches.models import Branch

# Supplier imports (self)
from .models import Supplier

# Product imports
from products.models import Product

# Sales imports
from sales.models import SaleItem

@login_required
def supplier_list(request):
    """List all suppliers - filtered by branch with performance metrics"""
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
    
    suppliers = Supplier.objects.all()
    
    if current_branch:
        suppliers = suppliers.filter(product__branch=current_branch).distinct()
    elif not (request.user.is_superuser or request.user.role == 'admin'):
        suppliers = suppliers.none()
    
    suppliers = suppliers.order_by('name')
    
    total_suppliers = suppliers.count()
    total_products = 0
    total_products_sold = 0
    total_sales_amount = Decimal('0.00')
    
    for supplier in suppliers:
        total_products += supplier.total_products
        total_products_sold += supplier.total_products_sold
        total_sales_amount += supplier.total_sales_amount
    
    search_query = request.GET.get('search', '')
    if search_query:
        suppliers = suppliers.filter(
            Q(name__icontains=search_query) |
            Q(contact_person__icontains=search_query) |
            Q(phone__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    context = {
        'suppliers': suppliers,
        'total_suppliers': total_suppliers,
        'total_products': total_products,
        'total_products_sold': total_products_sold,
        'total_sales_amount': total_sales_amount,
        'search_query': search_query,
        'current_branch': current_branch,
        'viewing_all_branches': current_branch is None and (request.user.is_superuser or request.user.role == 'admin')
    }
    return render(request, 'suppliers/supplier_list.html', context)

@login_required
def supplier_detail(request, pk):
    """Supplier detail view with full analytics"""
    supplier = get_object_or_404(Supplier, id=pk)
    
    products = supplier.product_set.all().select_related('category', 'branch')
    
    total_products = products.count()
    total_products_sold = supplier.total_products_sold
    total_sales_amount = supplier.total_sales_amount
    total_profit = supplier.total_profit
    
    product_analytics = []
    for product in products:
        sale_items = SaleItem.objects.filter(product=product)
        
        quantity_sold = sale_items.aggregate(total=Sum('quantity'))['total'] or 0
        revenue = sale_items.aggregate(total=Sum('total'))['total'] or Decimal('0.00')
        cost_of_goods = product.cost_price * Decimal(str(quantity_sold))
        profit = revenue - cost_of_goods
        
        product_analytics.append({
            'product': product,
            'quantity_sold': quantity_sold,
            'revenue': revenue,
            'cost': cost_of_goods,
            'profit': profit,
            'current_stock': product.quantity,
            'low_stock': product.is_low_stock,
        })
    
    product_analytics.sort(key=lambda x: x['revenue'], reverse=True)
    
    branches = Branch.objects.filter(
        products__supplier=supplier
    ).distinct()
    
    context = {
        'supplier': supplier,
        'products': products,
        'product_analytics': product_analytics,
        'total_products': total_products,
        'total_products_sold': total_products_sold,
        'total_sales_amount': total_sales_amount,
        'total_profit': total_profit,
        'branches': branches,
        'low_stock_count': supplier.low_stock_products.count(),
        'out_of_stock_count': supplier.out_of_stock_products.count(),
    }
    return render(request, 'suppliers/supplier_detail.html', context)

@login_required
def add_supplier(request):
    if request.method == 'POST':
        try:
            name = request.POST.get('name', '').strip()
            contact_person = request.POST.get('contact_person', '').strip()
            email = request.POST.get('email', '').strip()
            phone = request.POST.get('phone', '').strip()
            address = request.POST.get('address', '').strip()
            website = request.POST.get('website', '').strip()
            notes = request.POST.get('notes', '').strip()
            is_active = request.POST.get('is_active', '1') == '1'
            
            if not name:
                messages.error(request, 'Supplier name is required')
                return render(request, 'suppliers/supplier_form.html', {'action': 'Add'})
            
            if not phone:
                messages.error(request, 'Phone number is required')
                return render(request, 'suppliers/supplier_form.html', {'action': 'Add'})
            
            supplier = Supplier.objects.create(
                name=name,
                contact_person=contact_person,
                email=email,
                phone=phone,
                address=address,
                website=website if website else None,
                notes=notes,
                is_active=is_active
            )
            
            messages.success(request, f'Supplier "{supplier.name}" added successfully!')
            return redirect('supplier_list')
            
        except Exception as e:
            messages.error(request, f'Error adding supplier: {str(e)}')
            return render(request, 'suppliers/supplier_form.html', {'action': 'Add'})
    
    return render(request, 'suppliers/supplier_form.html', {'action': 'Add'})

@login_required
def edit_supplier(request, pk):
    supplier = get_object_or_404(Supplier, id=pk)
    
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
    
    if request.method == 'POST':
        try:
            supplier.name = request.POST.get('name', '').strip()
            supplier.contact_person = request.POST.get('contact_person', '').strip()
            supplier.email = request.POST.get('email', '').strip()
            supplier.phone = request.POST.get('phone', '').strip()
            supplier.address = request.POST.get('address', '').strip()
            supplier.website = request.POST.get('website', '').strip()
            supplier.notes = request.POST.get('notes', '').strip()
            supplier.is_active = request.POST.get('is_active', '1') == '1'
            
            if not supplier.name:
                messages.error(request, 'Supplier name is required')
                return render(request, 'suppliers/supplier_form.html', {
                    'supplier': supplier,
                    'action': 'Edit',
                    'current_branch': current_branch
                })
            
            if not supplier.phone:
                messages.error(request, 'Phone number is required')
                return render(request, 'suppliers/supplier_form.html', {
                    'supplier': supplier,
                    'action': 'Edit',
                    'current_branch': current_branch
                })
            
            supplier.save()
            
            messages.success(request, f'Supplier "{supplier.name}" updated successfully!')
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'supplier_id': supplier.id,
                    'supplier_name': supplier.name
                })
            else:
                return redirect('supplier_list')
            
        except Exception as e:
            error_msg = f'Error updating supplier: {str(e)}'
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': error_msg})
            else:
                messages.error(request, error_msg)
                return render(request, 'suppliers/supplier_form.html', {
                    'supplier': supplier,
                    'action': 'Edit',
                    'current_branch': current_branch
                })
    
    context = {
        'supplier': supplier,
        'action': 'Edit',
        'current_branch': current_branch,
    }
    return render(request, 'suppliers/supplier_form.html', context)

@login_required
def delete_supplier(request, pk):
    if request.method == 'POST':
        supplier = get_object_or_404(Supplier, id=pk)
        
        if not (request.user.is_superuser or request.user.role == 'admin'):
            if request.user.branch and supplier.product_set.filter(branch=request.user.branch).exists():
                return JsonResponse({'success': False, 'error': 'This supplier has products in your branch. Remove products first.'})
        
        supplier.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid method'})