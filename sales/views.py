from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, Sum
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
import json
import uuid
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

# inventoryApp imports
from inventoryApp.models import User, UserNotification
from inventoryApp.utils import safe_decimal

# Branch imports
from branches.models import Branch

# Product imports
from products.models import Product, Category

# Customer imports
from customers.models import Customer

# Sales imports (self)
from .models import Sale, SaleItem, Payment, StockMovement, PendingCart, SavedCart

@login_required
def home(request):
    """POS view - shows products for current branch"""
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
    
    products = Product.objects.filter(quantity__gt=0)
    if current_branch:
        products = products.filter(branch=current_branch)
    products = products.order_by('name')
    
    categories = Category.objects.all()
    pending_cart = PendingCart.objects.filter(staff=request.user).first()
    
    context = {
        'products': products,
        'categories': categories,
        'pending_cart': pending_cart.cart_data if pending_cart else None,
        'now': timezone.now(),
        'current_branch': current_branch,
        'branch_name': current_branch.name if current_branch else "All Branches"
    }
    return render(request, 'sales/home.html', context)

@login_required
def view_receipt(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id)
    items = sale.items.all()
    payments = sale.payments.all()
    
    item_discounts_total = sum(item.discount for item in items)
    payment_method = payments.last().payment_method if payments.exists() else 'cash'
    
    context = {
        'sale': sale,
        'items': items,
        'payments': payments,
        'payment_method': payment_method,
        'item_discounts_total': item_discounts_total,
    }
    return render(request, 'sales/receipt.html', context)

@login_required
def sale_history(request):
    """Sales history with date filtering and search"""
    # --- FIX: Get all filter parameters ---
    search_query = request.GET.get('search', '')
    page_number = request.GET.get('page', 1)
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    # --- FIX END ---
    
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
    sales = Sale.objects.all().select_related('staff', 'branch').order_by('-created_at')
    
    # Apply branch filter
    if current_branch:
        sales = sales.filter(branch=current_branch)
    elif not (request.user.is_superuser or request.user.role == 'admin'):
        sales = sales.none()
    
    # --- FIX: Apply date range filter ---
    if date_from and date_to:
        try:
            start_date = datetime.strptime(date_from, '%Y-%m-%d').date()
            end_date = datetime.strptime(date_to, '%Y-%m-%d').date() + timedelta(days=1)
            sales = sales.filter(created_at__range=[start_date, end_date])
        except ValueError:
            pass
    # --- FIX END ---
    
    # Apply search filter
    if search_query:
        sales = sales.filter(
            Q(invoice_number__icontains=search_query) |
            Q(customer_name__icontains=search_query) |
            Q(customer_phone__icontains=search_query) |
            Q(staff__username__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(sales, 50)
    
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    
    page_total = sum(float(sale.total) for sale in page_obj.object_list)
    
    context = {
        'page_obj': page_obj,
        'sales': page_obj.object_list,
        'search_query': search_query,
        'page_total': page_total,
        'total_sales_count': sales.count(),
        'current_branch': current_branch,
        'viewing_all_branches': current_branch is None and (request.user.is_superuser or request.user.role == 'admin'),
        # --- FIX: Pass dates back to template ---
        'date_from': date_from,
        'date_to': date_to,
        # --- FIX END ---
    }
    return render(request, 'sales/sale_history.html', context)

@login_required
def sale_history_search_api(request):
    """API endpoint for sales history search"""
    search_term = request.GET.get('q', '').strip()
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
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
    sales = Sale.objects.all().select_related('staff', 'branch').order_by('-created_at')
    
    # Filter by branch
    if current_branch:
        sales = sales.filter(branch=current_branch)
    elif not (request.user.is_superuser or request.user.role == 'admin'):
        sales = sales.none()
    
    # Filter by date range
    if date_from and date_to:
        try:
            start_date = datetime.strptime(date_from, '%Y-%m-%d').date()
            end_date = datetime.strptime(date_to, '%Y-%m-%d').date() + timedelta(days=1)
            sales = sales.filter(created_at__range=[start_date, end_date])
        except ValueError:
            pass
    
    # Filter by search term
    if search_term:
        sales = sales.filter(
            Q(invoice_number__icontains=search_term) |
            Q(customer_name__icontains=search_term) |
            Q(customer_phone__icontains=search_term) |
            Q(staff__username__icontains=search_term)
        )
    
    sales = sales[:100]
    
    results = []
    for sale in sales:
        results.append({
            'id': sale.id,
            'invoice_number': sale.invoice_number,
            'customer_name': sale.customer_name or 'Walk-in',
            'customer_phone': sale.customer_phone or '',
            'staff_name': sale.staff.username if sale.staff else 'Unknown',
            'subtotal': float(sale.subtotal),
            'discount': float(sale.discount),
            'total': float(sale.total),
            'amount_paid': float(sale.amount_paid),
            'balance': float(sale.balance),
            'payment_status': sale.payment_status,
            'created_at': sale.created_at.isoformat(),
        })
    
    return JsonResponse({
        'success': True,
        'results': results,
        'count': len(results),
    })

@login_required
@csrf_exempt
def process_sale(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            saved_cart_id = data.get('saved_cart_id')
            saved_cart = None
            
            if saved_cart_id:
                try:
                    saved_cart = SavedCart.objects.get(id=saved_cart_id, staff=request.user)
                except SavedCart.DoesNotExist:
                    saved_cart = None
            
            if not data.get('items'):
                return JsonResponse({'success': False, 'error': 'No items in cart'})
            
            customer_name = data.get('customer_name', '').strip()
            customer_phone = data.get('customer_phone', '').strip()
            
            if not customer_name:
                customer_name = "Walk-in Customer"
            
            # Get current branch
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
            
            if not current_branch:
                return JsonResponse({
                    'success': False, 
                    'error': 'No branch selected. Please select a branch before processing a sale.'
                })
            
            # Customer handling
            if customer_phone:
                customer, created = Customer.objects.get_or_create(
                    phone=customer_phone,
                    defaults={
                        'name': customer_name,
                        'customer_type': 'regular',
                        'branch': current_branch
                    }
                )
                if not created and customer.name != customer_name and customer_name != "Walk-in Customer":
                    customer.name = customer_name
                    customer.save()
                if customer.branch != current_branch:
                    customer.branch = current_branch
                    customer.save()
            else:
                customer = Customer.objects.create(
                    name=customer_name,
                    phone=f"WALKIN-{uuid.uuid4().hex[:8].upper()}",
                    customer_type='regular',
                    branch=current_branch
                )
            
            # Calculate totals
            subtotal = Decimal('0')
            item_discounts_total = Decimal('0')
            
            for item in data['items']:
                item_price = Decimal(str(item['price'])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                item_quantity = Decimal(str(item['quantity']))
                item_discount = Decimal(str(item.get('discount', 0))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                subtotal += (item_price * item_quantity)
                item_discounts_total += item_discount
            
            total = (subtotal - item_discounts_total).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            payments_data = data.get('payments', [])
            total_paid = Decimal('0')
            
            if payments_data:
                for payment in payments_data:
                    amount = Decimal(str(payment.get('amount', 0))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    total_paid += amount
            else:
                total_paid = Decimal(str(data.get('amount_paid', 0))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            balance = (total - total_paid).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            if balance < Decimal('0'):
                balance = Decimal('0')
            
            # Check stock for each item BEFORE processing
            for item in data['items']:
                try:
                    product = Product.objects.get(id=item['product_id'])
                    # FIX: Ensure quantity is integer
                    item_quantity = int(item['quantity'])
                    if product.quantity < item_quantity:
                        return JsonResponse({
                            'success': False, 
                            'error': f'Insufficient stock for {product.name}. Available: {product.quantity}, Requested: {item_quantity}'
                        })
                except Product.DoesNotExist:
                    return JsonResponse({'success': False, 'error': f'Product ID {item["product_id"]} not found'})
            
            # Generate invoice number
            today_str = timezone.now().strftime('%Y%m%d')
            invoice_number = f"INV-{today_str}-{uuid.uuid4().hex[:6].upper()}"
            
            if balance <= Decimal('0'):
                payment_status = 'paid'
            elif balance < total:
                payment_status = 'partial'
            else:
                payment_status = 'unpaid'
            
            # Create Sale
            sale = Sale.objects.create(
                invoice_number=invoice_number,
                staff=request.user,
                customer_name=customer_name,
                customer_phone=customer_phone,
                subtotal=subtotal,
                discount=item_discounts_total,
                total=total,
                amount_paid=total_paid,
                balance=balance,
                payment_status=payment_status,
                branch=current_branch
            )
            
            # Update customer stats
            customer.total_purchases += total
            customer.last_purchase_date = timezone.now()
            customer.loyalty_points += int(total / 10)
            customer.save()
            
            # ========== PROCESS EACH ITEM ==========
            for item in data.get('items', []):
                product = Product.objects.get(id=item['product_id'])
                
                # FIX: Use integer for quantity
                item_quantity = int(item['quantity'])
                
                item_price = Decimal(str(item['price'])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                item_discount = Decimal(str(item.get('discount', 0))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                item_total = (item_price * Decimal(str(item_quantity))) - item_discount
                
                # Create SaleItem
                SaleItem.objects.create(
                    sale=sale,
                    product=product,
                    product_name=product.name,
                    quantity=item_quantity,
                    price=item_price,
                    discount=item_discount,
                    total=item_total
                )
                
                # FIX: Correctly reduce stock
                product.quantity -= item_quantity
                product.save()
                
                # Create StockMovement record
                StockMovement.objects.create(
                    product=product,
                    movement_type='out',
                    quantity=item_quantity,
                    reference=invoice_number,
                    notes=f"Sold in invoice {invoice_number}",
                    created_by=request.user
                )
            
            # ========== PROCESS PAYMENTS ==========
            if payments_data:
                for payment in payments_data:
                    amount = Decimal(str(payment.get('amount', 0))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    if amount > 0:
                        Payment.objects.create(
                            sale=sale,
                            amount=amount,
                            payment_method=payment.get('method', 'cash'),
                            reference=payment.get('reference', ''),
                            notes=payment.get('notes', ''),
                            created_by=request.user
                        )
            else:
                amount_paid = Decimal(str(data.get('amount_paid', 0))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                if amount_paid > 0:
                    Payment.objects.create(
                        sale=sale,
                        amount=amount_paid,
                        payment_method=data.get('payment_method', 'cash'),
                        reference=data.get('reference', ''),
                        notes=data.get('notes', ''),
                        created_by=request.user
                    )
            
            # Delete pending cart
            PendingCart.objects.filter(staff=request.user).delete()
            
            # Delete saved cart if used
            if saved_cart:
                saved_cart.delete()
                cart_deleted = True
            else:
                cart_deleted = False
            
            # Notifications
            UserNotification.create_notification(
                user=request.user,
                notification_type='sales',
                message=f'New sale: {invoice_number} - ₦{total:,.2f}',
                related_id=sale.id
            )
            
            admins = User.objects.filter(Q(role='admin') | Q(is_superuser=True))
            for admin in admins.distinct():
                if admin != request.user:
                    UserNotification.create_notification(
                        user=admin,
                        notification_type='dashboard',
                        message=f'New sale by {request.user.username}: {invoice_number}',
                        related_id=sale.id
                    )
            
            return JsonResponse({
                'success': True,
                'sale_id': sale.id,
                'invoice_number': invoice_number,
                'total': float(total),
                'balance': float(balance),
                'cart_deleted': cart_deleted,
                'cart_id': saved_cart_id if saved_cart else None,
                'customer_id': customer.id,
                'branch_name': current_branch.name
            })
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
@csrf_exempt
def save_pending_cart(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            if not data.get('items'):
                return JsonResponse({'success': False, 'error': 'Cart is empty'})
            
            subtotal = Decimal('0')
            for item in data['items']:
                item_price = Decimal(str(item.get('price', 0)))
                item_quantity = Decimal(str(item.get('quantity', 1)))
                item_discount = Decimal(str(item.get('discount', 0)))
                subtotal += (item_price * item_quantity) - item_discount
            
            cart_data = {
                'items': data['items'],
                'customer_name': data.get('customer_name', ''),
                'customer_phone': data.get('customer_phone', ''),
                'payment_type': data.get('payment_type', 'full'),
                'payment_method': data.get('payment_method', 'cash'),
                'amount_paid': float(data.get('amount_paid', 0)),
                'subtotal': float(subtotal),
                'total': float(subtotal),
                'timestamp': timezone.now().isoformat()
            }
            
            PendingCart.objects.filter(staff=request.user).delete()
            PendingCart.objects.create(staff=request.user, cart_data=cart_data)
            
            return JsonResponse({'success': True})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def load_pending_cart(request):
    try:
        pending_cart = PendingCart.objects.filter(staff=request.user).first()
        
        if pending_cart:
            return JsonResponse({
                'success': True,
                'cart_data': pending_cart.cart_data
            })
        else:
            return JsonResponse({
                'success': True,
                'cart_data': None
            })
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@csrf_exempt
def delete_pending_cart(request):
    if request.method == 'POST':
        try:
            PendingCart.objects.filter(staff=request.user).delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def saved_carts_list(request):
    """List saved carts - filtered by branch"""
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
    
    saved_carts = SavedCart.objects.filter(staff=request.user).order_by('-created_at')
    
    if current_branch:
        filtered_carts = []
        for cart in saved_carts:
            cart_data = cart.cart_data
            if cart_data and 'items' in cart_data:
                items = cart_data['items']
                for item in items:
                    if 'product_id' in item:
                        try:
                            product = Product.objects.get(id=item['product_id'])
                            if product.branch == current_branch:
                                filtered_carts.append(cart)
                                break
                        except Product.DoesNotExist:
                            continue
        saved_carts = filtered_carts
    
    context = {
        'saved_carts': saved_carts,
        'current_branch': current_branch,
        'viewing_all_branches': current_branch is None and (request.user.is_superuser or request.user.role == 'admin')
    }
    return render(request, 'sales/saved_carts_list.html', context)

@login_required
@csrf_exempt
def save_cart(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            cart_name = data.get('cart_name', f'Cart {timezone.now().strftime("%Y-%m-%d %H:%M")}')
            
            cart_data = data.get('cart_data', {})
            if not cart_data.get('items'):
                return JsonResponse({'success': False, 'error': 'Cart is empty'})
            
            items = cart_data.get('items', [])
            calculated_items = []
            subtotal = Decimal('0.00')
            
            for item in items:
                price = Decimal(str(item.get('price', 0))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                quantity = Decimal(str(item.get('quantity', 1)))
                discount = Decimal(str(item.get('discount', 0))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                item_total = (price * quantity) - discount
                item_total = item_total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                subtotal += item_total
                
                calculated_item = {
                    'id': item.get('id'),
                    'product_id': item.get('product_id'),
                    'name': item.get('name'),
                    'price': float(price),
                    'quantity': int(quantity),
                    'discount': float(discount),
                    'total': float(item_total)
                }
                calculated_items.append(calculated_item)
            
            prepared_cart_data = {
                'items': calculated_items,
                'customer_name': cart_data.get('customer_name', ''),
                'customer_phone': cart_data.get('customer_phone', ''),
                'payment_type': cart_data.get('payment_type', 'full'),
                'payment_method': cart_data.get('payment_method', 'cash'),
                'amount_paid': float(cart_data.get('amount_paid', 0)),
                'subtotal': float(subtotal),
                'total': float(subtotal),
                'timestamp': timezone.now().isoformat()
            }
            
            saved_cart = SavedCart.objects.create(
                staff=request.user,
                cart_name=cart_name,
                cart_data=prepared_cart_data
            )
            
            return JsonResponse({
                'success': True,
                'cart_id': saved_cart.id,
                'cart_name': saved_cart.cart_name,
                'total': float(subtotal)
            })
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def load_saved_cart(request, cart_id):
    try:
        saved_cart = SavedCart.objects.get(id=cart_id, staff=request.user)
        cart_data = saved_cart.cart_data
        
        if 'items' in cart_data:
            recalculated_total = Decimal('0.00')
            for item in cart_data['items']:
                price = Decimal(str(item.get('price', 0)))
                quantity = Decimal(str(item.get('quantity', 1)))
                discount = Decimal(str(item.get('discount', 0)))
                item_total = (price * quantity) - discount
                recalculated_total += item_total
                item['total'] = float(item_total)
            
            cart_data['subtotal'] = float(recalculated_total)
            cart_data['total'] = float(recalculated_total)
            saved_cart.cart_data = cart_data
            saved_cart.save()
        
        return JsonResponse({
            'success': True,
            'cart_data': cart_data,
            'cart_name': saved_cart.cart_name
        })
        
    except SavedCart.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Cart not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@csrf_exempt
def delete_saved_cart(request, cart_id):
    if request.method == 'POST':
        try:
            saved_cart = SavedCart.objects.get(id=cart_id, staff=request.user)
            saved_cart.delete()
            return JsonResponse({'success': True})
        except SavedCart.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Cart not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def view_saved_cart(request, cart_id):
    saved_cart = get_object_or_404(SavedCart, id=cart_id, staff=request.user)
    cart_data = saved_cart.cart_data
    items_count = len(cart_data.get('items', []))
    total_amount = Decimal('0.00')
    
    items_with_totals = []
    for item in cart_data.get('items', []):
        price = Decimal(str(item.get('price', 0)))
        quantity = Decimal(str(item.get('quantity', 1)))
        discount = Decimal(str(item.get('discount', 0)))
        item_total = (price * quantity) - discount
        item_total = item_total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total_amount += item_total
        
        item_with_total = item.copy()
        item_with_total['calculated_total'] = float(item_total)
        items_with_totals.append(item_with_total)
    
    cart_data['items'] = items_with_totals
    
    context = {
        'saved_cart': saved_cart,
        'cart_data': cart_data,
        'items_count': items_count,
        'total_amount': total_amount,
    }
    return render(request, 'sales/saved_cart_detail.html', context)

@login_required
def recent_sales_stats_api(request):
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    
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
    
    sales_query = Sale.objects.all()
    if current_branch:
        sales_query = sales_query.filter(branch=current_branch)
    elif not (request.user.is_superuser or request.user.role == 'admin'):
        sales_query = sales_query.none()
    
    today_sales = sales_query.filter(created_at__date=today).count()
    week_sales = sales_query.filter(created_at__date__gte=week_ago).count()
    staff_sales = sales_query.filter(staff=request.user, created_at__date=today).count()
    
    return JsonResponse({
        'success': True,
        'today_count': today_sales,
        'week_count': week_sales,
        'staff_count': staff_sales,
    })

@login_required
def recent_sales_api(request):
    """Get recent sales (last 24 hours) - filtered by branch"""
    try:
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
        
        yesterday = timezone.now() - timedelta(days=1)
        
        sales = Sale.objects.filter(
            created_at__gte=yesterday
        ).select_related('staff').prefetch_related('items').order_by('-created_at')[:20]
        
        if current_branch:
            sales = sales.filter(branch=current_branch)
        elif not (request.user.is_superuser or request.user.role == 'admin'):
            sales = sales.none()
        
        sales_data = []
        for sale in sales:
            staff_name = sale.staff.username if sale.staff else 'Unknown Staff'
            staff_full_name = f"{sale.staff.first_name or ''} {sale.staff.last_name or ''}".strip() if sale.staff else 'Unknown'
            
            items_data = []
            for item in sale.items.all():
                items_data.append({
                    'id': item.id,
                    'name': item.product_name,
                    'quantity': item.quantity,
                    'price': float(item.price),
                    'discount': float(item.discount),
                    'total': float(item.total),
                })
            
            sales_data.append({
                'id': sale.id,
                'invoice_number': sale.invoice_number,
                'customer_name': sale.customer_name or 'Walk-in Customer',
                'customer_phone': sale.customer_phone or '',
                'staff_name': staff_name,
                'staff_full_name': staff_full_name,
                'total': float(sale.total),
                'amount_paid': float(sale.amount_paid),
                'balance': float(sale.balance),
                'payment_status': sale.payment_status,
                'created_at': sale.created_at.isoformat(),
                'formatted_date': sale.created_at.strftime('%b %d, %I:%M %p'),
                'items': items_data,
            })
        
        return JsonResponse({
            'success': True,
            'sales': sales_data,
            'count': len(sales_data),
            'current_branch': current_branch.name if current_branch else 'All Branches'
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': str(e),
            'sales': []
        })

@login_required
def sale_details_api(request, pk):
    try:
        sale = Sale.objects.select_related('staff').prefetch_related('items').get(id=pk)
        
        items_data = []
        for item in sale.items.all():
            items_data.append({
                'id': item.id,
                'name': item.product_name,
                'quantity': item.quantity,
                'price': float(item.price),
                'discount': float(item.discount),
                'total': float(item.total),
            })
        
        sale_data = {
            'id': sale.id,
            'invoice_number': sale.invoice_number,
            'customer_name': sale.customer_name,
            'customer_phone': sale.customer_phone,
            'staff_name': sale.staff.username,
            'staff_full_name': f"{sale.staff.first_name or ''} {sale.staff.last_name or ''}".strip(),
            'total': float(sale.total),
            'amount_paid': float(sale.amount_paid),
            'balance': float(sale.balance),
            'payment_status': sale.payment_status,
            'created_at': sale.created_at.isoformat(),
            'formatted_date': sale.created_at.strftime('%b %d, %Y %I:%M %p'),
            'items': items_data,
        }
        
        return JsonResponse({
            'success': True,
            'sale': sale_data,
        })
        
    except Sale.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Sale not found',
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
        })

@login_required
def search_products_api(request):
    """API endpoint for real-time products search - filtered by branch"""
    search_term = request.GET.get('q', '').strip()
    
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
    products = Product.objects.filter(is_active=True).select_related('category', 'supplier').order_by('name')
    
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
        )[:50]  # Limit results
    
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
        'current_branch': current_branch.name if current_branch else 'All Branches'
    })

@login_required
def profit_stats_api(request):
    """API endpoint to get profit statistics for dashboard"""
    try:
        date_filter = request.GET.get('date_filter', 'today')
        today = timezone.now().date()
        
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
        
        sale_items = SaleItem.objects.filter(
            sale__created_at__range=[start_date, end_date]
        ).select_related('product', 'sale__branch')
        
        if current_branch:
            sale_items = sale_items.filter(sale__branch=current_branch)
        
        total_revenue = Decimal('0.00')
        total_cost = Decimal('0.00')
        
        daily_profit = {}
        branch_profit = {}
        
        for item in sale_items:
            sale_date = item.sale.created_at.date()
            date_str = sale_date.isoformat()
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
            
            total_revenue += item.total
            daily_profit[date_str]['revenue'] += item.total
            daily_profit[date_str]['items_sold'] += item.quantity
            
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
        
        total_profit = total_revenue - total_cost
        
        for date, data in daily_profit.items():
            data['profit'] = data['revenue'] - data['cost']
            data['revenue'] = float(data['revenue'])
            data['cost'] = float(data['cost'])
            data['profit'] = float(data['profit'])
        
        for branch, data in branch_profit.items():
            data['profit'] = data['revenue'] - data['cost']
            data['revenue'] = float(data['revenue'])
            data['cost'] = float(data['cost'])
            data['profit'] = float(data['profit'])
        
        daily_profit_list = sorted(daily_profit.values(), key=lambda x: x['date'])
        branch_profit_list = sorted(branch_profit.values(), key=lambda x: x['revenue'], reverse=True)
        
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