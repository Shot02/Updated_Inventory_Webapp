from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, F
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import json 
from django.conf import settings  
from django.views.decorators.csrf import csrf_exempt 

# Import from inventoryApp instead of core
from inventoryApp.models import User, UserNotification
from inventoryApp.utils import safe_decimal

from branches.models import Branch
from products.models import Product, Category
from sales.models import Sale, SaleItem, Payment
from suppliers.models import Supplier
from customers.models import Customer
from refunds.models import RefundRequest, Refund

@login_required
def admin_dashboard(request):
    """Admin dashboard with comprehensive statistics - accessible by admin and managers"""
    # Allow managers to access dashboard
    if request.user.role not in ['admin', 'manager'] and not request.user.is_superuser:
        messages.error(request, 'You do not have permission to access the dashboard.')
        return redirect('home')
    
    # --- FIX START: Get all filter parameters from request ---
    date_filter = request.GET.get('date_filter', 'today')
    custom_start = request.GET.get('custom_start')
    custom_end = request.GET.get('custom_end')
    sales_search = request.GET.get('sales_search', '')
    stock_search = request.GET.get('stock_search', '')
    # --- FIX END ---
    
    # Get current branch from session or user
    current_branch = None
    if request.user.is_superuser or request.user.role == 'admin':
        branch_id = request.session.get('current_branch_id')
        if branch_id:
            try:
                current_branch = Branch.objects.get(id=branch_id, is_active=True)
            except Branch.DoesNotExist:
                current_branch = None
    else:
        current_branch = request.user.branch
    
    # Calculate date range
    today = timezone.now().date()

    # --- FIX: Handle custom dates correctly ---
    if date_filter == 'today':
        start_date = today
        end_date = today
        query_end_date = today + timedelta(days=1)
    elif date_filter == 'week':
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
        query_end_date = end_date + timedelta(days=1)
    elif date_filter == 'month':
        start_date = today.replace(day=1)
        if start_date.month == 12:
            end_date = start_date.replace(year=start_date.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_date = start_date.replace(month=start_date.month + 1, day=1) - timedelta(days=1)
        query_end_date = end_date + timedelta(days=1)
    elif date_filter == 'year':
        start_date = today.replace(month=1, day=1)
        end_date = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        query_end_date = end_date + timedelta(days=1)
    elif date_filter == 'custom':
        # --- FIX: Use custom dates from request ---
        if custom_start and custom_end:
            try:
                start_date = datetime.strptime(custom_start, '%Y-%m-%d').date()
                end_date = datetime.strptime(custom_end, '%Y-%m-%d').date()
                query_end_date = end_date + timedelta(days=1)
            except ValueError:
                start_date = today
                end_date = today
                query_end_date = today + timedelta(days=1)
        else:
            start_date = today
            end_date = today
            query_end_date = today + timedelta(days=1)
    else:
        # Fallback for unknown filter
        start_date = today
        end_date = today
        query_end_date = today + timedelta(days=1)
    # --- FIX END ---
    
    # Base querysets with branch filtering
    products_query = Product.objects.all()
    sales_query = Sale.objects.all()
    payments_query = Payment.objects.all()
    sale_items_query = SaleItem.objects.all()
    
    # Apply branch filter
    if current_branch:
        products_query = products_query.filter(branch=current_branch)
        sales_query = sales_query.filter(branch=current_branch)
        payments_query = payments_query.filter(sale__branch=current_branch)
        sale_items_query = sale_items_query.filter(sale__branch=current_branch)
    elif not (request.user.is_superuser or request.user.role == 'admin' or request.user.role == 'manager'):
        products_query = products_query.none()
        sales_query = sales_query.none()
        payments_query = payments_query.none()
        sale_items_query = sale_items_query.none()
    
    # --- FIX: Apply date filter to ALL statistics ---
    total_products = products_query.count()
    total_sales = sales_query.filter(created_at__range=[start_date, query_end_date]).count()
    low_stock_products = products_query.filter(quantity__lte=F('reorder_level'), quantity__gt=0).count()
    
    # Debtors: Filter by date range
    debtors_count = sales_query.filter(
        balance__gt=0, 
        created_at__range=[start_date, query_end_date]
    ).count()
    
    # Payments: Filter by date range and payment method
    cash_payments = safe_decimal(payments_query.filter(
        payment_method='cash', created_at__range=[start_date, query_end_date]
    ).aggregate(total=Sum('amount'))['total'])
    
    transfer_payments = safe_decimal(payments_query.filter(
        payment_method='transfer', created_at__range=[start_date, query_end_date]
    ).aggregate(total=Sum('amount'))['total'])
    
    card_payments = safe_decimal(payments_query.filter(
        payment_method='card', created_at__range=[start_date, query_end_date]
    ).aggregate(total=Sum('amount'))['total'])
    
    total_payments = safe_decimal(payments_query.filter(
        created_at__range=[start_date, query_end_date]
    ).aggregate(total=Sum('amount'))['total'])
    
    total_revenue = max(total_payments, Decimal('0.00'))
    
    # ========== PROFIT CALCULATIONS ==========
    sales_in_range = sales_query.filter(
        created_at__range=[start_date, query_end_date]
    ).prefetch_related('items__product')
    
    total_revenue_from_sales = Decimal('0.00')
    total_cost_of_goods = Decimal('0.00')
    total_profit = Decimal('0.00')
    profit_margin_percentage = Decimal('0.00')
    
    for sale in sales_in_range:
        sale_revenue = Decimal('0.00')
        sale_cost = Decimal('0.00')
        
        for item in sale.items.all():
            item_revenue = safe_decimal(item.total)
            sale_revenue += item_revenue
            
            if item.product and item.product.cost_price:
                item_cost = safe_decimal(item.product.cost_price) * Decimal(str(item.quantity))
                sale_cost += item_cost
        
        total_revenue_from_sales += sale_revenue
        total_cost_of_goods += sale_cost
    
    total_profit = total_revenue_from_sales - total_cost_of_goods
    
    if total_revenue_from_sales > 0:
        profit_margin_percentage = (total_profit / total_revenue_from_sales) * 100
    else:
        profit_margin_percentage = Decimal('0.00')
    
    # Profit by payment method
    profit_by_payment = {
        'cash': Decimal('0.00'),
        'transfer': Decimal('0.00'),
        'card': Decimal('0.00'),
    }
    
    payments_in_range = payments_query.filter(
        created_at__range=[start_date, query_end_date],
        payment_method__in=['cash', 'transfer', 'card']
    ).select_related('sale')
    
    for payment in payments_in_range:
        if payment.sale and payment.sale.total > 0:
            sale_total = safe_decimal(payment.sale.total)
            payment_amount = safe_decimal(payment.amount)
            payment_ratio = payment_amount / sale_total
            
            for item in payment.sale.items.all().select_related('product'):
                item_revenue = safe_decimal(item.total) * payment_ratio
                item_cost = Decimal('0.00')
                
                if item.product and item.product.cost_price:
                    item_cost = safe_decimal(item.product.cost_price) * Decimal(str(item.quantity)) * payment_ratio
                
                profit_by_payment[payment.payment_method] += (item_revenue - item_cost)
    
    # Top 5 most profitable products
    top_profitable_products = []
    product_profit_map = {}
    
    for item in sale_items_query.filter(sale__created_at__range=[start_date, query_end_date]):
        if item.product:
            product_id = item.product.id
            if product_id not in product_profit_map:
                product_profit_map[product_id] = {
                    'name': item.product.name,
                    'sku': item.product.sku,
                    'revenue': Decimal('0.00'),
                    'cost': Decimal('0.00'),
                    'quantity_sold': 0,
                    'profit': Decimal('0.00')
                }
            
            product_profit_map[product_id]['revenue'] += safe_decimal(item.total)
            if item.product.cost_price:
                product_profit_map[product_id]['cost'] += safe_decimal(item.product.cost_price) * Decimal(str(item.quantity))
            product_profit_map[product_id]['quantity_sold'] += item.quantity
    
    for product_id, data in product_profit_map.items():
        data['profit'] = data['revenue'] - data['cost']
        if data['profit'] > 0:
            top_profitable_products.append(data)
    
    top_profitable_products = sorted(top_profitable_products, key=lambda x: x['profit'], reverse=True)[:5]
    
    # Recent sales
    recent_sales = sales_query.filter(
        created_at__range=[start_date, query_end_date]
    ).select_related('staff').order_by('-created_at')[:50]
    
    if sales_search:
        recent_sales = recent_sales.filter(
            Q(invoice_number__icontains=sales_search) |
            Q(customer_name__icontains=sales_search) |
            Q(staff__username__icontains=sales_search) |
            Q(customer_phone__icontains=sales_search)
        )[:50]
    
    # Low stock items
    low_stock = products_query.filter(
        quantity__lte=F('reorder_level'), quantity__gt=0
    ).select_related('category').order_by('quantity')[:50]
    
    if stock_search:
        low_stock = low_stock.filter(
            Q(name__icontains=stock_search) |
            Q(sku__icontains=stock_search) |
            Q(category__name__icontains=stock_search)
        )[:50]
    
    # Pending refund requests
    refunds_query = RefundRequest.objects.all()
    if current_branch:
        refunds_query = refunds_query.filter(sale__branch=current_branch)
    pending_refunds = refunds_query.filter(status='pending').count()
    
    # Today's refunds
    today_refunds = safe_decimal(Refund.objects.filter(
        processed_date__date=today
    ).aggregate(total=Sum('amount'))['total'])
    
    # --- FIX: Pass all filter parameters back to template ---
    context = {
        'date_filter': date_filter,
        'start_date': start_date,
        'end_date': end_date,
        'today': today,
        'total_products': total_products,
        'total_sales': total_sales,
        'low_stock_products': low_stock_products,
        'debtors_count': debtors_count,
        'cash_payments': cash_payments,
        'transfer_payments': transfer_payments,
        'card_payments': card_payments,
        'total_revenue': total_revenue,
        'total_profit': max(total_profit, Decimal('0.00')),
        'profit_margin': max(profit_margin_percentage, Decimal('0.00')),
        'total_cost_of_goods': total_cost_of_goods,
        'total_revenue_from_sales': total_revenue_from_sales,
        'profit_by_payment': profit_by_payment,
        'top_profitable_products': top_profitable_products,
        'recent_sales': recent_sales,
        'low_stock': low_stock,
        'sales_search': sales_search,
        'stock_search': stock_search,
        'pending_refunds': pending_refunds,
        'today_refunds': today_refunds,
        'current_branch': current_branch,
        'branch_name': current_branch.name if current_branch else "All Branches",
        'viewing_all_branches': current_branch is None and (request.user.is_superuser or request.user.role == 'admin'),
        'custom_start': custom_start,
        'custom_end': custom_end,
    }
    # --- FIX END ---
    
    if request.user.is_authenticated:
        UserNotification.mark_as_read(request.user, 'dashboard')
    
    return render(request, 'dashboard/admin_dashboard.html', context)

@login_required
def search_dashboard_api(request):
    """API endpoint for dashboard search (sales and stock)"""
    search_type = request.GET.get('type', 'sales')
    search_term = request.GET.get('q', '').strip()
    date_filter = request.GET.get('date_filter', 'today')
    custom_start = request.GET.get('custom_start')
    custom_end = request.GET.get('custom_end')
    
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
    
    # Calculate date range
    today = timezone.now().date()
    
    if date_filter == 'today':
        start_date = today
        end_date = today + timedelta(days=1)
    elif date_filter == 'week':
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=7)
    elif date_filter == 'month':
        start_date = today.replace(day=1)
        if start_date.month == 12:
            end_date = start_date.replace(year=start_date.year + 1, month=1, day=1)
        else:
            end_date = start_date.replace(month=start_date.month + 1, day=1)
    elif date_filter == 'year':
        start_date = today.replace(month=1, day=1)
        end_date = today.replace(year=today.year + 1, month=1, day=1)
    else:
        if custom_start and custom_end:
            try:
                start_date = datetime.strptime(custom_start, '%Y-%m-%d').date()
                end_date = datetime.strptime(custom_end, '%Y-%m-%d').date() + timedelta(days=1)
            except ValueError:
                start_date = today
                end_date = today + timedelta(days=1)
        else:
            start_date = today
            end_date = today + timedelta(days=1)
    
    results = []
    
    if search_type == 'sales':
        sales_query = Sale.objects.filter(created_at__range=[start_date, end_date])
        if current_branch:
            sales_query = sales_query.filter(branch=current_branch)
        
        if search_term:
            sales_query = sales_query.filter(
                Q(invoice_number__icontains=search_term) |
                Q(customer_name__icontains=search_term) |
                Q(staff__username__icontains=search_term) |
                Q(customer_phone__icontains=search_term)
            )
        
        for sale in sales_query[:50]:
            results.append({
                'id': sale.id,
                'invoice_number': sale.invoice_number,
                'customer_name': sale.customer_name or 'Walk-in',
                'staff_name': sale.staff.username if sale.staff else 'Unknown',
                'total': float(sale.total),
                'payment_status': sale.payment_status,
                'created_at': sale.created_at.isoformat(),
            })
    
    elif search_type == 'stock':
        stock_query = Product.objects.filter(quantity__lte=F('reorder_level'), quantity__gt=0)
        if current_branch:
            stock_query = stock_query.filter(branch=current_branch)
        
        if search_term:
            stock_query = stock_query.filter(
                Q(name__icontains=search_term) |
                Q(sku__icontains=search_term) |
                Q(category__name__icontains=search_term)
            )
        
        for product in stock_query[:50]:
            results.append({
                'id': product.id,
                'name': product.name,
                'sku': product.sku,
                'category': product.category.name if product.category else 'N/A',
                'quantity': product.quantity,
                'reorder_level': product.reorder_level,
            })
    
    return JsonResponse({
        'success': True,
        'results': results,
        'count': len(results),
    })
    
@login_required
def profit_stats_api(request):
    """API endpoint to get profit statistics for dashboard"""
    try:
        # Get date range from request
        date_filter = request.GET.get('date_filter', 'today')
        today = timezone.now().date()
        
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
        
        # Calculate date range
        if date_filter == 'today':
            start_date = today
            end_date = today + timedelta(days=1)
        elif date_filter == 'week':
            start_date = today - timedelta(days=today.weekday())
            end_date = start_date + timedelta(days=7)
        elif date_filter == 'month':
            start_date = today.replace(day=1)
            if start_date.month == 12:
                end_date = start_date.replace(year=start_date.year + 1, month=1, day=1)
            else:
                end_date = start_date.replace(month=start_date.month + 1, day=1)
        elif date_filter == 'year':
            start_date = today.replace(month=1, day=1)
            end_date = today.replace(year=today.year + 1, month=1, day=1)
        else:
            custom_start = request.GET.get('custom_start')
            custom_end = request.GET.get('custom_end')
            if custom_start and custom_end:
                start_date = datetime.strptime(custom_start, '%Y-%m-%d').date()
                end_date = datetime.strptime(custom_end, '%Y-%m-%d').date() + timedelta(days=1)
            else:
                start_date = today
                end_date = today + timedelta(days=1)
        
        # Get sale items in range
        sale_items = SaleItem.objects.filter(
            sale__created_at__range=[start_date, end_date]
        ).select_related('product', 'sale__branch')
        
        # Filter by branch if switched
        if current_branch:
            sale_items = sale_items.filter(sale__branch=current_branch)
        
        # Calculate totals
        total_revenue = Decimal('0.00')
        total_cost = Decimal('0.00')
        
        # Daily profit data - grouped by branch
        daily_profit = {}
        branch_profit = {}
        
        for item in sale_items:
            # Get sale date for grouping
            sale_date = item.sale.created_at.date()
            date_str = sale_date.isoformat()
            
            # Get branch name
            branch_name = item.sale.branch.name if item.sale.branch else 'No Branch'
            
            if date_str not in daily_profit:
                daily_profit[date_str] = {
                    'date': date_str,
                    'branch': branch_name,
                    'revenue': Decimal('0.00'),
                    'cost': Decimal('0.00'),
                    'profit': Decimal('0.00'),
                    'items_sold': 0
                }
            
            # Add to daily totals
            total_revenue += item.total
            daily_profit[date_str]['revenue'] += item.total
            daily_profit[date_str]['items_sold'] += item.quantity
            
            # Branch-specific profit
            if branch_name not in branch_profit:
                branch_profit[branch_name] = {
                    'branch': branch_name,
                    'revenue': Decimal('0.00'),
                    'cost': Decimal('0.00'),
                    'profit': Decimal('0.00'),
                    'items_sold': 0
                }
            
            branch_profit[branch_name]['revenue'] += item.total
            branch_profit[branch_name]['items_sold'] += item.quantity
            
            if item.product:
                item_cost = item.product.cost_price * Decimal(str(item.quantity))
                total_cost += item_cost
                daily_profit[date_str]['cost'] += item_cost
                branch_profit[branch_name]['cost'] += item_cost
        
        # Calculate profit
        total_profit = total_revenue - total_cost
        
        # Calculate daily profit
        for date, data in daily_profit.items():
            data['profit'] = data['revenue'] - data['cost']
            data['revenue'] = float(data['revenue'])
            data['cost'] = float(data['cost'])
            data['profit'] = float(data['profit'])
        
        # Calculate branch profit
        for branch, data in branch_profit.items():
            data['profit'] = data['revenue'] - data['cost']
            data['revenue'] = float(data['revenue'])
            data['cost'] = float(data['cost'])
            data['profit'] = float(data['profit'])
        
        # Sort daily profit by date
        daily_profit_list = sorted(daily_profit.values(), key=lambda x: x['date'])
        
        # Sort branch profit by revenue
        branch_profit_list = sorted(branch_profit.values(), key=lambda x: x['revenue'], reverse=True)
        
        # Calculate profit margin
        profit_margin = 0
        if total_revenue > 0:
            profit_margin = float((total_profit / total_revenue) * 100)
        
        return JsonResponse({
            'success': True,
            'total_revenue': float(total_revenue),
            'total_cost': float(total_cost),
            'total_profit': float(total_profit),
            'profit_margin': profit_margin,
            'daily_profit': daily_profit_list,
            'branch_profit': branch_profit_list,
            'items_sold_count': sale_items.count(),
            'current_branch': current_branch.name if current_branch else 'All Branches'
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
        
@login_required
@csrf_exempt
def mark_notifications_read(request):
    """Mark notifications as read for a specific type"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            notification_type = data.get('notification_type')
            
            if notification_type in ['dashboard', 'debtors', 'refunds', 'sales']:
                UserNotification.mark_as_read(request.user, notification_type)
                return JsonResponse({'success': True})
            
            return JsonResponse({'success': False, 'error': 'Invalid notification type'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
@csrf_exempt
def refresh_session(request):
    """Refresh the user's session to prevent timeout"""
    if request.method == 'POST':
        request.session['last_activity'] = timezone.now().isoformat()
        request.session.set_expiry(settings.SESSION_COOKIE_AGE)
        return JsonResponse({
            'success': True,
            'message': 'Session refreshed successfully'
        })
    return JsonResponse({'success': False, 'error': 'Invalid request method'})