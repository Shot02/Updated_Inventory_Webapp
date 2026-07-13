from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, Sum
from decimal import Decimal

# Import from inventoryApp instead of core
from inventoryApp.models import User, UserNotification
from inventoryApp.utils import safe_decimal

from branches.models import Branch
from sales.models import Sale, Payment
from customers.models import Customer

@login_required
def debtors_list(request):
    """List of debtors grouped by customer - NO LIMIT"""
    from decimal import Decimal
    from django.db.models import Q, Sum
    
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
    
    # Get all sales with balance > 0 - NO LIMIT
    all_sales = Sale.objects.filter(balance__gt=0)
    
    if current_branch:
        all_sales = all_sales.filter(branch=current_branch)
    elif not (request.user.is_superuser or request.user.role == 'admin'):
        all_sales = all_sales.none()
    
    all_sales = all_sales.select_related('staff').prefetch_related('payments').order_by('-created_at')
    
    # Group sales by customer
    customer_debts = {}
    for sale in all_sales:
        # Calculate net paid (excluding refunds)
        non_refund_payments = sale.payments.filter(
            ~Q(payment_method='refund')
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        refunds = sale.payments.filter(
            payment_method='refund'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        net_paid = non_refund_payments + refunds
        
        # Only include if customer actually owes money
        if net_paid < sale.total:
            customer_key = sale.customer_phone or sale.customer_name or 'unknown'
            
            if customer_key not in customer_debts:
                customer_debts[customer_key] = {
                    'customer_name': sale.customer_name or 'Walk-in Customer',
                    'customer_phone': sale.customer_phone or '',
                    'total_balance': Decimal('0.00'),
                    'total_owed': Decimal('0.00'),
                    'total_paid': Decimal('0.00'),
                    'sales': [],
                    'sale_count': 0,
                    'customer_key': customer_key
                }
            
            customer_debts[customer_key]['sales'].append(sale)
            customer_debts[customer_key]['sale_count'] += 1
            customer_debts[customer_key]['total_balance'] += sale.balance
            customer_debts[customer_key]['total_owed'] += sale.total
            customer_debts[customer_key]['total_paid'] += sale.amount_paid
    
    # Convert to list and sort by total balance
    debtors_list = list(customer_debts.values())
    debtors_list.sort(key=lambda x: x['total_balance'], reverse=True)
    
    search_query = request.GET.get('search', '')
    if search_query:
        filtered_debtors = []
        for debtor in debtors_list:
            if (search_query.lower() in debtor['customer_name'].lower() or
                search_query.lower() in debtor['customer_phone'].lower()):
                filtered_debtors.append(debtor)
        debtors_list = filtered_debtors
    
    context = {
        'debtors': debtors_list,  # ALL debtors, no limit
        'search_query': search_query,
        'current_branch': current_branch,
        'viewing_all_branches': current_branch is None and (request.user.is_superuser or request.user.role == 'admin'),
        'total_debtors': len(debtors_list)
    }
    return render(request, 'debtors/debtors_list.html', context)

@login_required
@csrf_exempt
def record_bulk_payment(request):
    """Record payment for all debts of a customer"""
    if request.method == 'POST':
        try:
            customer_name = request.POST.get('customer_name', '').strip()
            customer_phone = request.POST.get('customer_phone', '').strip()
            amount = Decimal(request.POST.get('amount', 0))
            payment_method = request.POST.get('payment_method', 'cash')
            reference = request.POST.get('reference', '')
            notes = request.POST.get('notes', '')
            
            if amount <= 0:
                messages.error(request, 'Amount must be greater than 0')
                return redirect('debtors_list')
            
            # Get all sales for this customer with balance > 0
            sales = Sale.objects.filter(
                Q(customer_name__iexact=customer_name) | Q(customer_phone__iexact=customer_phone),
                balance__gt=0
            ).order_by('created_at')
            
            if not sales.exists():
                messages.error(request, 'No debts found for this customer')
                return redirect('debtors_list')
            
            # Check if amount exceeds total balance
            total_balance = sales.aggregate(total=Sum('balance'))['total'] or Decimal('0.00')
            if amount > total_balance:
                messages.error(request, f'Amount cannot exceed total balance of ₦{total_balance:,.2f}')
                return redirect('debtors_list')
            
            # Distribute payment across sales (oldest first)
            remaining_amount = amount
            for sale in sales:
                if remaining_amount <= 0:
                    break
                
                payment_amount = min(remaining_amount, sale.balance)
                if payment_amount > 0:
                    # Create payment record
                    Payment.objects.create(
                        sale=sale,
                        amount=payment_amount,
                        payment_method=payment_method,
                        reference=reference,
                        notes=notes,
                        created_by=request.user
                    )
                    
                    # Update sale
                    sale.amount_paid += payment_amount
                    sale.balance = sale.total - sale.amount_paid
                    if sale.balance <= 0:
                        sale.payment_status = 'paid'
                    else:
                        sale.payment_status = 'partial'
                    sale.save()
                    
                    remaining_amount -= payment_amount
            
            messages.success(request, f'Payment of ₦{amount:,.2f} recorded successfully!')
            return redirect('debtors_list')
            
        except Exception as e:
            messages.error(request, f'Error recording payment: {str(e)}')
            return redirect('debtors_list')
    
    return redirect('debtors_list')

@login_required
def debtor_detail(request, customer_phone):
    """Display all debts for a specific customer using phone as unique identifier"""
    from decimal import Decimal
    from django.db.models import Q, Sum
    
    # Get current branch from session or user
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
    
    # Get all sales for this customer with balance > 0
    sales = Sale.objects.filter(
        customer_phone__iexact=customer_phone,
        balance__gt=0
    ).select_related('staff').prefetch_related('payments').order_by('-created_at')
    
    # Apply branch filter
    if current_branch:
        sales = sales.filter(branch=current_branch)
    elif not (request.user.is_superuser or request.user.role == 'admin'):
        sales = sales.none()
    
    # Get customer name from the most recent sale
    customer_name = sales.first().customer_name if sales.exists() else 'Unknown Customer'
    
    # Calculate totals
    total_balance = sales.aggregate(total=Sum('balance'))['total'] or Decimal('0.00')
    total_owed = sales.aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    total_paid = sales.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
    
    context = {
        'customer_name': customer_name,
        'customer_phone': customer_phone,
        'sales': sales,
        'total_balance': total_balance,
        'total_owed': total_owed,
        'total_paid': total_paid,
        'sale_count': sales.count(),
        'current_branch': current_branch,
    }
    return render(request, 'debtors/debtor_detail.html', context)

@login_required
def record_payment(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id)
    
    current_branch = request.user.branch
    if current_branch and not request.user.is_superuser:
        if sale.branch != current_branch:
            messages.error(request, 'You cannot record payment for a sale from another branch.')
            return redirect('debtors_list')
    
    if request.method == 'POST':
        try:
            amount = Decimal(request.POST.get('amount', 0))
            payment_method = request.POST.get('payment_method', 'cash')
            reference = request.POST.get('reference', '')
            notes = request.POST.get('notes', '')
            
            if amount <= 0:
                messages.error(request, 'Amount must be greater than 0')
                return redirect('record_payment', sale_id=sale_id)
            
            if amount > sale.balance:
                messages.error(request, f'Amount cannot exceed balance of ₦{sale.balance:,.2f}')
                return redirect('record_payment', sale_id=sale_id)
            
            Payment.objects.create(
                sale=sale,
                amount=amount,
                payment_method=payment_method,
                reference=reference,
                notes=notes,
                created_by=request.user
            )
            
            sale.amount_paid += amount
            sale.balance = sale.total - sale.amount_paid
            
            if sale.balance <= 0:
                sale.payment_status = 'paid'
            else:
                sale.payment_status = 'partial'
            
            sale.save()
            
            if sale.balance > 0:
                UserNotification.create_notification(
                    user=request.user,
                    notification_type='debtors',
                    message=f'Partial payment on {sale.invoice_number} - Balance: ₦{sale.balance:,.2f}',
                    related_id=sale.id
                )
            else:
                UserNotification.mark_as_read(request.user, 'debtors')
            
            admins = User.objects.filter(Q(role='admin') | Q(is_superuser=True))
            for admin in admins.distinct():
                if admin != request.user:
                    UserNotification.create_notification(
                        user=admin,
                        notification_type='dashboard',
                        message=f'Payment recorded by {request.user.username} on {sale.invoice_number}',
                        related_id=sale.id
                    )
            
            messages.success(request, f'Payment of ₦{amount:,.2f} recorded successfully!')
            return redirect('debtors_list')
            
        except Exception as e:
            messages.error(request, f'Error recording payment: {str(e)}')
    
    context = {
        'sale': sale,
    }
    return render(request, 'debtors/record_payment.html', context)