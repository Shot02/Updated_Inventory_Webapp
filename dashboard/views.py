from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, F
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal

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
    # Allow managers to access dashboard
    if request.user.role not in ['admin', 'manager'] and not request.user.is_superuser:
        messages.error(request, 'You do not have permission to access the dashboard.')
        return redirect('pos')
    
    date_filter = request.GET.get('date_filter', 'today')
    
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
    
    today = timezone.now().date()

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
    else:
        custom_start = request.GET.get('custom_start')
        custom_end = request.GET.get('custom_end')
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
    
    products_query = Product.objects.all()
    sales_query = Sale.objects.all()
    payments_query = Payment.objects.all()
    sale_items_query = SaleItem.objects.all()
    
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
    
    total_products = products_query.count()
    total_sales = sales_query.filter(created_at__range=[start_date, query_end_date]).count()
    low_stock_products = products_query.filter(quantity__lte=F('reorder_level'), quantity__gt=0).count()
    debtors_count = sales_query.filter(balance__gt=0, created_at__range=[start_date, query_end_date]).count()
    
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
    
    # ========== PROFIT CALCULATIONS (FIXED) ==========
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
    
    sales_search = request.GET.get('sales_search', '')
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
    
    stock_search = request.GET.get('stock_search', '')
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
        'viewing_all_branches': current_branch is None and (request.user.is_superuser or request.user.role == 'admin')
    }
    
    if request.user.is_authenticated:
        UserNotification.mark_as_read(request.user, 'dashboard')
    
    return render(request, 'dashboard/admin_dashboard.html', context)