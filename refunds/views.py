from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, Sum
from decimal import Decimal

# inventoryApp imports
from inventoryApp.models import User, UserNotification
from inventoryApp.utils import safe_decimal

# Branch imports
from branches.models import Branch

# Sales imports
from sales.models import Sale, SaleItem, Payment, StockMovement

# Product imports
from products.models import Product

# Refund imports (self)
from .models import RefundRequest, Refund

@login_required
def refund_list(request):
    if request.user.is_authenticated:
        UserNotification.mark_as_read(request.user, 'refunds')
    
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
    
    if request.user.role == 'admin' or request.user.is_superuser:
        refunds = Refund.objects.all().select_related(
            'sale', 'processed_by', 'refund_request', 'refund_request__created_by'
        ).order_by('-processed_date')
    else:
        refunds = Refund.objects.filter(
            refund_request__created_by=request.user
        ).select_related(
            'sale', 'processed_by', 'refund_request', 'refund_request__created_by'
        ).order_by('-processed_date')
    
    if current_branch and not request.user.is_superuser:
        refunds = refunds.filter(sale__branch=current_branch)
    
    context = {'refunds': refunds}
    return render(request, 'refunds/refund_list.html', context)

@login_required
def refund_requests_list(request):
    """List of all refund requests - filtered by branch with permissions"""
    if request.user.is_authenticated:
        UserNotification.mark_as_read(request.user, 'refunds')
    
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
    
    if request.user.role == 'admin' or request.user.is_superuser:
        refunds = RefundRequest.objects.all().select_related(
            'sale', 'created_by', 'approved_by'
        ).order_by('-request_date')
        if current_branch:
            refunds = refunds.filter(sale__branch=current_branch)
    else:
        refunds = RefundRequest.objects.filter(
            created_by=request.user
        ).select_related(
            'sale', 'created_by', 'approved_by'
        ).order_by('-request_date')
        if current_branch:
            refunds = refunds.filter(sale__branch=current_branch)
    
    pending_count = refunds.filter(status='pending').count()
    approved_count = refunds.filter(status='approved').count()
    declined_count = refunds.filter(status='declined').count()
    total_count = refunds.count()
    
    context = {
        'refunds': refunds,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'declined_count': declined_count,
        'total_count': total_count,
        'current_branch': current_branch,
        'viewing_all_branches': current_branch is None and (request.user.is_superuser or request.user.role == 'admin'),
        'user_role': request.user.role,
    }
    return render(request, 'refunds/refund_requests_list.html', context)

@login_required
def refund_details_api(request, pk):
    """API endpoint to get refund details"""
    try:
        refund = RefundRequest.objects.get(id=pk)
        
        if not (refund.created_by == request.user or request.user.role == 'admin' or request.user.is_superuser):
            return JsonResponse({'success': False, 'error': 'Access denied'})
        
        refund_data = {
            'id': refund.id,
            'customer_name': refund.customer_name,
            'customer_phone': refund.customer_phone,
            'reason': refund.reason,
            'amount': float(refund.amount),
            'status': refund.status,
            'request_date': refund.request_date.isoformat(),
            'sale_invoice': refund.sale.invoice_number if refund.sale else None,
            'approved_by': refund.approved_by.get_full_name() if refund.approved_by else None,
            'approved_date': refund.approved_date.isoformat() if refund.approved_date else None,
            'created_by': refund.created_by.get_full_name() or refund.created_by.username,
        }
        
        return JsonResponse({'success': True, 'refund': refund_data})
        
    except RefundRequest.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Refund not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def create_refund_request(request):
    """Create new refund request with transaction selection - filtered by branch"""
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
    recent_sales = Sale.objects.filter(
        created_at__gte=yesterday
    ).select_related('staff').prefetch_related('items').order_by('-created_at')
    
    if current_branch:
        recent_sales = recent_sales.filter(branch=current_branch)
    elif not (request.user.is_superuser or request.user.role == 'admin'):
        recent_sales = recent_sales.none()
    
    if request.method == 'POST':
        try:
            customer_name = request.POST.get('customer_name', '').strip()
            customer_phone = request.POST.get('customer_phone', '').strip()
            reason = request.POST.get('reason', '').strip()
            sale_id = request.POST.get('sale_id')
            sale_item_id = request.POST.get('sale_item_id')
            amount = request.POST.get('amount', '0').strip()
            refund_method = request.POST.get('refund_method', '')
            
            if not reason or not amount:
                messages.error(request, 'Reason and amount are required')
                return redirect('create_refund_request')
            
            try:
                refund_amount = Decimal(amount)
                if refund_amount <= 0:
                    messages.error(request, 'Refund amount must be greater than 0')
                    return redirect('create_refund_request')
            except (InvalidOperation, ValueError):
                messages.error(request, 'Invalid refund amount')
                return redirect('create_refund_request')
            
            selected_sale = None
            selected_item = None
            
            if sale_id and sale_id != '':
                try:
                    selected_sale = Sale.objects.get(id=sale_id)
                    if current_branch and selected_sale.branch != current_branch:
                        messages.error(request, 'This sale belongs to a different branch')
                        return redirect('create_refund_request')
                    
                    if sale_item_id and sale_item_id != '':
                        try:
                            selected_item = SaleItem.objects.get(id=sale_item_id, sale=selected_sale)
                            max_refund = selected_item.total
                            if refund_amount > max_refund:
                                messages.error(request, f'Refund amount cannot exceed item total (₦{max_refund:,.2f})')
                                return redirect('create_refund_request')
                        except SaleItem.DoesNotExist:
                            messages.error(request, 'Selected item not found')
                            return redirect('create_refund_request')
                    else:
                        max_refund = selected_sale.amount_paid
                        if refund_amount > max_refund:
                            messages.error(request, f'Refund amount cannot exceed paid amount (₦{max_refund:,.2f})')
                            return redirect('create_refund_request')
                    
                except Sale.DoesNotExist:
                    messages.error(request, 'Selected sale not found')
                    return redirect('create_refund_request')
            else:
                if not customer_name or not customer_phone:
                    messages.error(request, 'Customer name and phone are required when no sale is selected')
                    return redirect('create_refund_request')
                
                customer_sales = Sale.objects.filter(
                    Q(customer_name__iexact=customer_name) | Q(customer_phone__iexact=customer_phone)
                ).order_by('-created_at')
                
                if current_branch:
                    customer_sales = customer_sales.filter(branch=current_branch)
                
                if not customer_sales.exists():
                    messages.error(request, f'No sales found for customer: {customer_name} in this branch')
                    return redirect('create_refund_request')
                
                for sale in customer_sales:
                    if sale.amount_paid >= refund_amount:
                        selected_sale = sale
                        break
                
                if not selected_sale:
                    messages.error(request, f'No sale found with sufficient paid amount for refund of ₦{refund_amount:,.2f}')
                    return redirect('create_refund_request')
            
            refund_request = RefundRequest.objects.create(
                customer_name=customer_name if customer_name else (selected_sale.customer_name or 'Unknown Customer'),
                customer_phone=customer_phone if customer_phone else (selected_sale.customer_phone or ''),
                reason=reason,
                amount=refund_amount,
                sale=selected_sale,
                sale_item=selected_item,
                created_by=request.user
            )
            
            if selected_item:
                refund_request.original_amount = selected_item.total
            elif selected_sale:
                refund_request.original_amount = selected_sale.amount_paid
            refund_request.save()
            
            admins = User.objects.filter(Q(role='admin') | Q(is_superuser=True)).distinct()
            for admin in admins:
                if admin != request.user:
                    UserNotification.create_notification(
                        user=admin,
                        notification_type='refunds',
                        message=f'New refund request: {refund_request.customer_name} - ₦{refund_request.amount:,.2f}',
                        related_id=refund_request.id
                    )
            
            UserNotification.create_notification(
                user=request.user,
                notification_type='refunds',
                message=f'Your refund request #{refund_request.id} has been submitted for approval',
                related_id=refund_request.id
            )
            
            messages.success(request, f'Refund request #{refund_request.id} created successfully! Pending admin approval.')
            return redirect('refund_requests_list')
            
        except Exception as e:
            messages.error(request, f'Error creating refund request: {str(e)}')
            return redirect('create_refund_request')
    
    context = {
        'action': 'Create',
        'current_branch': current_branch,
        'recent_sales': recent_sales,
    }
    return render(request, 'refunds/refund_request_form.html', context)

@login_required
@csrf_exempt
def edit_refund_request(request, pk):
    refund = get_object_or_404(RefundRequest, id=pk)
    
    if not refund.can_edit() or (refund.created_by != request.user and request.user.role != 'admin'):
        return JsonResponse({'success': False, 'error': 'You cannot edit this refund request'})
    
    if request.method == 'POST':
        try:
            refund.customer_name = request.POST.get('customer_name')
            refund.customer_phone = request.POST.get('customer_phone')
            refund.reason = request.POST.get('reason')
            
            new_amount = Decimal(request.POST.get('amount'))
            
            if refund.sale_item and new_amount > refund.sale_item.total:
                return JsonResponse({'success': False, 'error': f'Amount cannot exceed item total (₦{refund.sale_item.total:,.2f})'})
            elif refund.sale and new_amount > refund.sale.total:
                return JsonResponse({'success': False, 'error': f'Amount cannot exceed sale total (₦{refund.sale.total:,.2f})'})
            
            refund.amount = new_amount
            refund.save()
            
            return JsonResponse({'success': True})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
@csrf_exempt
def approve_refund_request(request, pk):
    if request.method == 'POST':
        try:
            if not (request.user.role == 'admin' or request.user.is_superuser):
                messages.error(request, 'Only admins can approve refunds')
                return redirect('refund_requests_list')
            
            refund_request = RefundRequest.objects.get(id=pk)
            
            if refund_request.status != 'pending':
                messages.error(request, 'This refund request has already been processed')
                return redirect('refund_requests_list')
            
            if refund_request.refund_processed:
                messages.error(request, 'This refund has already been processed')
                return redirect('refund_requests_list')
            
            from decimal import Decimal, ROUND_HALF_UP
            
            sale = refund_request.sale
            if not sale:
                sales = Sale.objects.filter(
                    Q(customer_name__iexact=refund_request.customer_name) |
                    Q(customer_phone__iexact=refund_request.customer_phone)
                ).order_by('-created_at')
                
                if sales.exists():
                    sale = sales.first()
            
            if not sale:
                messages.error(request, 'No sale found for this refund request')
                return redirect('refund_requests_list')
            
            refund_amount = Decimal(str(refund_request.amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            if refund_amount <= Decimal('0'):
                messages.error(request, 'Refund amount must be greater than 0')
                return redirect('refund_requests_list')
            
            original_payments_total = sale.payments.filter(
                ~Q(payment_method='refund')
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            existing_refunds_total = abs(sale.payments.filter(
                payment_method='refund'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00'))
            
            max_refundable = original_payments_total - existing_refunds_total
            
            if refund_amount > max_refundable:
                messages.error(request, 
                    f'Refund amount (₦{refund_amount:,.2f}) exceeds available amount (₦{max_refundable:,.2f})'
                )
                return redirect('refund_requests_list')
            
            refund = Refund.objects.create(
                sale=sale,
                refund_request=refund_request,
                amount=refund_amount,
                reason=refund_request.reason,
                payment_method='refund',
                processed_by=request.user
            )
            
            refund_request.sale = sale
            refund_request.status = 'approved'
            refund_request.approved_by = request.user
            refund_request.approved_date = timezone.now()
            refund_request.refund_processed = True
            refund_request.save()
            
            Payment.objects.create(
                sale=sale,
                amount=-refund_amount,
                payment_method='refund',
                reference=f"REFUND-{refund_request.id}",
                notes=f"Refund processed: {refund_request.reason}",
                created_by=request.user
            )
            
            if refund_request.sale_item and refund_request.sale_item.product:
                item = refund_request.sale_item
                product = item.product
                
                if item.total > Decimal('0'):
                    refund_proportion = refund_amount / item.total
                    quantity_to_return = int(round(float(item.quantity) * float(refund_proportion)))
                    
                    if quantity_to_return > 0:
                        product.quantity += quantity_to_return
                        product.save()
                        
                        StockMovement.objects.create(
                            product=product,
                            movement_type='in',
                            quantity=quantity_to_return,
                            reference=f"REFUND-{refund_request.id}",
                            notes=f"Partial refund for {sale.invoice_number}",
                            created_by=request.user
                        )
            
            messages.success(request, f'Refund of ₦{refund_amount:,.2f} processed successfully!')
            
            if request.user.is_authenticated:
                UserNotification.mark_as_read(request.user, 'refunds')
            
            return redirect('refund_requests_list')
            
        except RefundRequest.DoesNotExist:
            messages.error(request, 'Refund request not found')
        except Exception as e:
            import traceback
            traceback.print_exc()
            messages.error(request, f'Error processing refund: {str(e)}')
    
    return redirect('refund_requests_list')

@login_required
@csrf_exempt
def decline_refund_request(request, pk):
    if request.method == 'POST':
        try:
            if not (request.user.role == 'admin' or request.user.is_superuser):
                messages.error(request, 'Only admins can decline refunds')
                return redirect('refund_requests_list')
            
            refund_request = RefundRequest.objects.get(id=pk)
            
            if refund_request.status != 'pending':
                messages.error(request, 'This refund request has already been processed')
                return redirect('refund_requests_list')
            
            refund_request.status = 'declined'
            refund_request.approved_by = request.user
            refund_request.approved_date = timezone.now()
            refund_request.save()
            
            messages.success(request, 'Refund request declined')
            
        except RefundRequest.DoesNotExist:
            messages.error(request, 'Refund request not found')
        except Exception as e:
            messages.error(request, f'Error declining refund: {str(e)}')
    
    return redirect('refund_requests_list')

@login_required
def get_refund_stats(request):
    today = timezone.now().date()
    
    today_refunds = Refund.objects.filter(processed_date__date=today).aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')
    
    pending_requests = RefundRequest.objects.filter(status='pending').count()
    
    month_start = today.replace(day=1)
    month_refunds = Refund.objects.filter(
        processed_date__date__gte=month_start
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    return JsonResponse({
        'today_refunds': float(today_refunds),
        'pending_requests': pending_requests,
        'month_refunds': float(month_refunds),
    })

@login_required
@csrf_exempt
def delete_refund_request(request, pk):
    if request.method == 'POST':
        try:
            if not (request.user.role == 'admin' or request.user.is_superuser):
                return JsonResponse({'success': False, 'error': 'Only admins can delete refund requests'})
            
            refund_request = RefundRequest.objects.get(id=pk)
            refund_request.delete()
            
            return JsonResponse({'success': True})
            
        except RefundRequest.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Refund request not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})