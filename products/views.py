from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Sum, F
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from inventoryApp.utils import safe_decimal
from .models import Product, Category
from suppliers.models import Supplier
from branches.models import Branch
from sales.models import SaleItem

@login_required
def product_list(request):
    """List all products - filtered by branch"""
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
    
    date_filter = request.GET.get('date_filter', 'all')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    selected_product_id = request.GET.get('product', '')

    products = Product.objects.all().select_related('category', 'supplier', 'branch')

    if current_branch:
        products = products.filter(branch=current_branch)
    elif not (request.user.is_superuser or request.user.role == 'admin'):
        products = products.none()

    filter_products = products.order_by('name')

    selected_product = None
    if selected_product_id:
        try:
            selected_product = products.get(id=int(selected_product_id))
            products = products.filter(id=selected_product.id)
        except (Product.DoesNotExist, ValueError, TypeError):
            selected_product_id = ''

    products = products.order_by('-created_at')

    sale_items = SaleItem.objects.filter(product__in=products)

    if date_filter == 'today':
        today = timezone.now().date()
        sale_items = sale_items.filter(sale__created_at__date=today)
    elif date_filter == 'week':
        week_ago = timezone.now().date() - timedelta(days=7)
        sale_items = sale_items.filter(sale__created_at__date__gte=week_ago)
    elif date_filter == 'month':
        month_ago = timezone.now().date() - timedelta(days=30)
        sale_items = sale_items.filter(sale__created_at__date__gte=month_ago)
    elif date_filter == 'custom' and start_date and end_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
            sale_items = sale_items.filter(sale__created_at__date__range=[start, end])
        except ValueError:
            pass

    # ========== STATS CALCULATIONS ==========
    
    # 1. Total In Stock (Quantity)
    total_in_stock = products.aggregate(total=Sum('quantity'))['total'] or 0
    
    # 2. Total Sales Count (Items Sold)
    total_sales_count = sale_items.aggregate(total=Sum('quantity'))['total'] or 0
    
    # 3. Total Sales Amount (Revenue)
    total_sales_amount = sale_items.aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    
    # 4. Total Inventory Value (Price × Quantity)
    total_inventory_value = Decimal('0.00')
    for product in products:
        total_inventory_value += (product.price * Decimal(str(product.quantity)))
    
    search_query = request.GET.get('search', '').strip()
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(sku__icontains=search_query) |
            Q(category__name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(supplier__name__icontains=search_query)
        )[:50]
    
    categories = Category.objects.all()
    suppliers = Supplier.objects.all()
    
    context = {
        'products': products,
        'search_query': search_query,
        'categories': categories,
        'suppliers': suppliers,
        'current_branch': current_branch,
        'viewing_all_branches': current_branch is None and (request.user.is_superuser or request.user.role == 'admin'),
        'total_in_stock': total_in_stock,
        'total_sales_count': total_sales_count,
        'total_sales_amount': total_sales_amount,
        'total_inventory_value': total_inventory_value,  # NEW
        'date_filter': date_filter,
        'start_date': start_date,
        'end_date': end_date,
        'filter_products': filter_products,
        'selected_product_id': selected_product_id,
        'selected_product': selected_product,
    }
    return render(request, 'products/product_list.html', context)

@login_required
def add_product(request):
    if request.method == 'POST':
        try:
            name = request.POST.get('name', 'Unnamed Product')
            category_id = request.POST.get('category')
            supplier_id = request.POST.get('supplier')
            new_supplier_name = request.POST.get('new_supplier', '').strip()
            description = request.POST.get('description', '')
            price = request.POST.get('price')
            cost_price = request.POST.get('cost_price')
            quantity = request.POST.get('quantity')
            reorder_level = request.POST.get('reorder_level')
            image = request.FILES.get('image')
            
            category = None
            if category_id:
                try:
                    category = Category.objects.get(id=category_id)
                except (Category.DoesNotExist, ValueError):
                    pass
            
            supplier = None
            if new_supplier_name:
                supplier, created = Supplier.objects.get_or_create(
                    name=new_supplier_name,
                    defaults={'phone': '0000000000', 'contact_person': 'Unknown'}
                )
            elif supplier_id:
                try:
                    supplier = Supplier.objects.get(id=supplier_id)
                except (Supplier.DoesNotExist, ValueError):
                    pass
            
            try:
                price_decimal = Decimal(price) if price else Decimal('0.00')
            except (InvalidOperation, TypeError, ValueError):
                price_decimal = Decimal('0.00')
            
            try:
                cost_price_decimal = Decimal(cost_price) if cost_price else Decimal('0.00')
            except (InvalidOperation, TypeError, ValueError):
                cost_price_decimal = Decimal('0.00')
            
            try:
                quantity_int = int(quantity) if quantity else 0
            except ValueError:
                quantity_int = 0
            
            try:
                reorder_level_int = int(reorder_level) if reorder_level else 10
            except ValueError:
                reorder_level_int = 10
            
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
            
            product = Product.objects.create(
                name=name,
                category=category,
                supplier=supplier,
                description=description,
                price=price_decimal,
                cost_price=cost_price_decimal,
                quantity=quantity_int,
                reorder_level=reorder_level_int,
                branch=current_branch
            )
            
            if image:
                product.image = image
                product.save()
            
            messages.success(request, f'Product "{name}" added successfully!')
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Product added successfully!',
                    'product_id': product.id,
                    'product_name': product.name,
                })
            else:
                return redirect('product_list')
            
        except Exception as e:
            messages.error(request, f'Error adding product: {str(e)}')
            return redirect('add_product')
    
    categories = Category.objects.all()
    suppliers = Supplier.objects.all()
    
    context = {
        'categories': categories,
        'suppliers': suppliers,
    }
    return render(request, 'products/product_form.html', context)

@login_required
def edit_product(request, pk):
    product = get_object_or_404(Product, id=pk)
    
    if request.method == 'POST':
        try:
            product.name = request.POST.get('name', 'Unnamed Product')
            product.description = request.POST.get('description', '')
            
            category_id = request.POST.get('category')
            new_category = request.POST.get('new_category', '').strip()
            
            if new_category:
                category, created = Category.objects.get_or_create(name=new_category)
                product.category = category
            elif category_id:
                try:
                    product.category = Category.objects.get(id=category_id)
                except (Category.DoesNotExist, ValueError):
                    product.category = None
            else:
                product.category = None
            
            supplier_id = request.POST.get('supplier')
            new_supplier_name = request.POST.get('new_supplier', '').strip()
            
            if new_supplier_name:
                supplier, created = Supplier.objects.get_or_create(
                    name=new_supplier_name,
                    defaults={'phone': '0000000000', 'contact_person': 'Unknown'}
                )
                product.supplier = supplier
            elif supplier_id:
                try:
                    product.supplier = Supplier.objects.get(id=supplier_id)
                except (Supplier.DoesNotExist, ValueError):
                    product.supplier = None
            else:
                product.supplier = None
            
            manufacturing_date = request.POST.get('manufacturing_date')
            if manufacturing_date:
                try:
                    product.manufacturing_date = datetime.strptime(manufacturing_date, '%Y-%m-%d').date()
                except ValueError:
                    product.manufacturing_date = None
            else:
                product.manufacturing_date = None
            
            expiry_date = request.POST.get('expiry_date')
            if expiry_date:
                try:
                    product.expiry_date = datetime.strptime(expiry_date, '%Y-%m-%d').date()
                except ValueError:
                    product.expiry_date = None
            else:
                product.expiry_date = None
            
            product.batch_number = request.POST.get('batch_number', '')
            product.location = request.POST.get('location', '')
            
            try:
                price_val = request.POST.get('price')
                product.price = Decimal(price_val) if price_val else Decimal('0.00')
            except (InvalidOperation, TypeError, ValueError):
                product.price = Decimal('0.00')
            
            try:
                cost_price_val = request.POST.get('cost_price')
                product.cost_price = Decimal(cost_price_val) if cost_price_val else Decimal('0.00')
            except (InvalidOperation, TypeError, ValueError):
                product.cost_price = Decimal('0.00')
            
            try:
                quantity_val = request.POST.get('quantity')
                product.quantity = int(quantity_val) if quantity_val else 0
            except ValueError:
                product.quantity = 0
            
            try:
                reorder_val = request.POST.get('reorder_level')
                product.reorder_level = int(reorder_val) if reorder_val else 10
            except ValueError:
                product.reorder_level = 10
            
            if 'image' in request.FILES:
                if product.image:
                    product.image.delete(save=False)
                product.image = request.FILES['image']
            
            if request.POST.get('clear_image') == '1':
                if product.image:
                    product.image.delete(save=False)
                product.image = None
            
            if request.user.is_superuser or request.user.role == 'admin':
                branch_id = request.POST.get('branch')
                if branch_id:
                    try:
                        new_branch = Branch.objects.get(id=branch_id)
                        product.branch = new_branch
                    except Branch.DoesNotExist:
                        pass
                elif branch_id == '':
                    product.branch = None
            
            product.save()
            
            messages.success(request, f'Product "{product.name}" updated successfully!')
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Product updated successfully!',
                    'product_id': product.id,
                    'product_name': product.name,
                    'branch_id': product.branch.id if product.branch else None,
                    'branch_name': product.branch.name if product.branch else None,
                })
            else:
                return redirect('product_list')
            
        except Exception as e:
            error_msg = f'Error updating product: {str(e)}'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': error_msg})
            else:
                messages.error(request, error_msg)
                return redirect('edit_product', pk=pk)
    
    categories = Category.objects.all()
    suppliers = Supplier.objects.all()
    all_branches = Branch.objects.filter(is_active=True).order_by('name')
    
    context = {
        'product': product,
        'categories': categories,
        'suppliers': suppliers,
        'all_branches': all_branches,
        'action': 'Edit',
    }
    return render(request, 'products/product_form.html', context)

@login_required
def delete_product(request, pk):
    product = get_object_or_404(Product, id=pk)
    
    if not (request.user.is_superuser or request.user.role == 'admin'):
        if request.user.branch and product.branch != request.user.branch:
            messages.error(request, 'You cannot delete products from another branch.')
            return redirect('product_list')
    
    if request.method == 'POST':
        product_name = product.name
        if product.image:
            product.image.delete(save=False)
        product.delete()
        messages.success(request, f'Product "{product_name}" deleted successfully!')
        return redirect('product_list')
    
    return render(request, 'products/product_confirm_delete.html', {'product': product})

@login_required
def search_products_api(request):
    """API endpoint for real-time product search with stats"""
    search_term = request.GET.get('q', '').strip()
    date_filter = request.GET.get('date_filter', 'all')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    # Get current branch
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
    
    # Base query
    products = Product.objects.all().select_related('category', 'supplier', 'branch')
    
    # Filter by branch
    if current_branch:
        products = products.filter(branch=current_branch)
    elif not (request.user.is_superuser or request.user.role == 'admin'):
        products = products.none()
    
    # Filter by search term
    if search_term:
        products = products.filter(
            Q(name__icontains=search_term) |
            Q(sku__icontains=search_term) |
            Q(category__name__icontains=search_term) |
            Q(supplier__name__icontains=search_term)
        )
    
    products = products.order_by('name')[:50]
    
    # ========== STATS CALCULATIONS ==========
    
    sale_items = SaleItem.objects.filter(product__in=products)
    
    if date_filter == 'today':
        from django.utils import timezone
        today = timezone.now().date()
        sale_items = sale_items.filter(sale__created_at__date=today)
    elif date_filter == 'week':
        from datetime import timedelta
        week_ago = timezone.now().date() - timedelta(days=7)
        sale_items = sale_items.filter(sale__created_at__date__gte=week_ago)
    elif date_filter == 'month':
        from datetime import timedelta
        month_ago = timezone.now().date() - timedelta(days=30)
        sale_items = sale_items.filter(sale__created_at__date__gte=month_ago)
    elif date_filter == 'custom' and start_date and end_date:
        from datetime import datetime
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
            sale_items = sale_items.filter(sale__created_at__date__range=[start, end])
        except ValueError:
            pass
    
    # 1. Total In Stock (Quantity)
    total_in_stock = products.aggregate(total=Sum('quantity'))['total'] or 0
    
    # 2. Total Sales Count (Items Sold)
    total_sales_count = sale_items.aggregate(total=Sum('quantity'))['total'] or 0
    
    # 3. Total Sales Amount (Revenue)
    total_sales_amount = sale_items.aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    
    # 4. Total Inventory Value (Price × Quantity)
    total_inventory_value = Decimal('0.00')
    for product in products:
        total_inventory_value += (product.price * Decimal(str(product.quantity)))
    
    # Format results
    results = []
    for product in products:
        results.append({
            'id': product.id,
            'name': product.name,
            'sku': product.sku,
            'price': float(product.price),
            'quantity': product.quantity,
            'image': product.image.url if product.image else '',
            'category': product.category.name if product.category else 'N/A',
            'supplier': product.supplier.name if product.supplier else 'N/A',
            'is_low_stock': product.quantity <= product.reorder_level,
        })
    
    return JsonResponse({
        'success': True,
        'results': results,
        'count': len(results),
        'stats': {
            'total_in_stock': total_in_stock,
            'total_sales_count': total_sales_count,
            'total_sales_amount': float(total_sales_amount),
            'total_inventory_value': float(total_inventory_value),  # NEW
        },
        'current_branch': current_branch.name if current_branch else 'All Branches'
    })
    


@login_required
def expiring_products_api(request):
    """API endpoint to get expiring and expired products"""
    from django.utils import timezone
    from datetime import timedelta
    
    today = timezone.now().date()
    thirty_days = today + timedelta(days=30)
    
    # Get current branch
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
    
    # Base queryset
    products = Product.objects.filter(
        expiry_date__isnull=False,
        quantity__gt=0
    )
    
    # Filter by branch
    if current_branch:
        products = products.filter(branch=current_branch)
    elif not (request.user.is_superuser or request.user.role == 'admin'):
        products = products.none()
    
    # Expiring soon (within 30 days)
    expiring_soon = products.filter(
        expiry_date__lte=thirty_days,
        expiry_date__gte=today
    ).values('id', 'name', 'sku', 'expiry_date', 'quantity')
    
    # Expired (past expiry date)
    expired = products.filter(
        expiry_date__lt=today
    ).values('id', 'name', 'sku', 'expiry_date', 'quantity')
    
    return JsonResponse({
        'success': True,
        'expiring_soon': list(expiring_soon),
        'expired': list(expired),
        'expiring_soon_count': expiring_soon.count(),
        'expired_count': expired.count(),
    })