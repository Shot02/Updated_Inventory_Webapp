from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q

# Core imports
from inventoryApp.models import User, UserNotification

# Branch imports
from branches.models import Branch

# Sales imports
from sales.models import SavedCart, PendingCart, Sale, Payment, StockMovement

# Refund imports
from refunds.models import RefundRequest, Refund

@login_required
def register_staff(request):
    if not (request.user.role == 'admin' or request.user.is_superuser):
        messages.error(request, 'Only admins can register staff')
        return redirect('pos')
    
    branches = Branch.objects.filter(is_active=True).order_by('name')
    
    if request.method == 'POST':
        try:
            username = request.POST.get('username')
            email = request.POST.get('email')
            first_name = request.POST.get('first_name')
            last_name = request.POST.get('last_name')
            password = request.POST.get('password')
            role = request.POST.get('role', 'staff')
            phone = request.POST.get('phone', '')
            branch_id = request.POST.get('branch')
            
            if not username or not email or not password:
                messages.error(request, 'Username, email and password are required')
                return redirect('register_staff')
            
            if User.objects.filter(username=username).exists():
                messages.error(request, 'Username already exists')
                return redirect('register_staff')
            
            branch = None
            if branch_id:
                try:
                    branch = Branch.objects.get(id=branch_id, is_active=True)
                except Branch.DoesNotExist:
                    messages.error(request, 'Selected branch does not exist')
                    return redirect('register_staff')
            
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role=role,
                phone=phone,
                is_staff=True,
                branch=branch
            )
            
            messages.success(request, f'Staff member "{username}" created successfully! Branch: {branch.name if branch else "Not assigned"}')
            return redirect('staff_list')
            
        except Exception as e:
            messages.error(request, f'Error creating staff: {str(e)}')
    
    context = {'branches': branches}
    return render(request, 'staff/register_staff.html', context)

@login_required
def staff_list(request):
    if not (request.user.role == 'admin' or request.user.is_superuser or request.user.role == 'manager'):
        messages.error(request, 'Only admins and managers can view staff list')
        return redirect('pos')
    
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
    
    staff = User.objects.filter(is_staff=True).order_by('-date_joined')
    
    if request.user.role == 'manager':
        staff = staff.filter(branch=current_branch)
    elif current_branch:
        staff = staff.filter(branch=current_branch)
    
    search_query = request.GET.get('search', '')
    if search_query:
        staff = staff.filter(
            Q(username__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone__icontains=search_query) |
            Q(role__icontains=search_query)
        )[:50]
    
    branches = Branch.objects.filter(is_active=True).order_by('name') if request.user.is_superuser or request.user.role == 'admin' else []
    
    context = {
        'staff': staff,
        'search_query': search_query,
        'branches': branches,
        'user_role': request.user.role,
        'current_branch': current_branch,
        'viewing_all_branches': current_branch is None and (request.user.is_superuser or request.user.role == 'admin')
    }
    return render(request, 'staff/staff_list.html', context)

@login_required
@csrf_exempt
def edit_staff(request):
    """Handle AJAX request to edit staff member - ADMIN ONLY"""
    if not (request.user.role == 'admin' or request.user.is_superuser):
        return JsonResponse({'success': False, 'error': 'Only admins can edit staff'})
    
    if request.method == 'POST':
        try:
            user_id = request.POST.get('user_id')
            user = User.objects.get(id=user_id)
            
            update_fields = []
            fields_to_update = ['username', 'email', 'first_name', 'last_name', 'phone', 'role', 'is_active', 'branch']
            
            for field in fields_to_update:
                if field == 'role':
                    new_value = request.POST.get('role')
                    if new_value and new_value != user.role:
                        user.role = new_value
                        update_fields.append('role')
                elif field == 'is_active':
                    is_active = request.POST.get('is_active')
                    if is_active is not None:
                        new_value = is_active == 'true'
                        if new_value != user.is_active:
                            user.is_active = new_value
                            update_fields.append('is_active')
                elif field == 'branch':
                    branch_id = request.POST.get('branch')
                    if branch_id:
                        try:
                            new_branch = Branch.objects.get(id=branch_id)
                            if user.branch != new_branch:
                                user.branch = new_branch
                                update_fields.append('branch')
                        except Branch.DoesNotExist:
                            return JsonResponse({'success': False, 'error': 'Branch not found'})
                    else:
                        if user.branch is not None:
                            user.branch = None
                            update_fields.append('branch')
                else:
                    new_value = request.POST.get(field, getattr(user, field))
                    if new_value != getattr(user, field):
                        setattr(user, field, new_value)
                        update_fields.append(field)
            
            if update_fields:
                user.save(update_fields=update_fields)
            
            # Auto-update branch manager if role changed to manager
            if 'role' in update_fields and user.role == 'manager' and user.branch:
                user.branch.manager = user.get_full_name() or user.username
                user.branch.save()
            
            # Handle password separately
            password = request.POST.get('password')
            if password and password.strip():
                user.set_password(password)
                user.save(update_fields=['password'])
                
                if user == request.user:
                    from django.contrib.auth import update_session_auth_hash
                    update_session_auth_hash(request, user)
            
            return JsonResponse({'success': True})
            
        except Exception as e:
            import traceback
            print(f"Error editing staff: {str(e)}")
            print(traceback.format_exc())
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
@csrf_exempt
def delete_staff(request, pk):
    if not (request.user.role == 'admin' or request.user.is_superuser):
        return JsonResponse({'success': False, 'error': 'Only admins can delete staff'})
    
    if request.method == 'POST':
        try:
            staff_member = get_object_or_404(User, id=pk)
            
            if staff_member == request.user:
                return JsonResponse({'success': False, 'error': 'You cannot delete your own account'})
            
            username = staff_member.username
            
            SavedCart.objects.filter(staff=staff_member).delete()
            PendingCart.objects.filter(staff=staff_member).delete()
            UserNotification.objects.filter(user=staff_member).delete()
            RefundRequest.objects.filter(created_by=staff_member).update(created_by=None)
            RefundRequest.objects.filter(approved_by=staff_member).update(approved_by=None)
            Refund.objects.filter(processed_by=staff_member).update(processed_by=None)
            Sale.objects.filter(staff=staff_member).update(staff=None)
            Payment.objects.filter(created_by=staff_member).update(created_by=None)
            StockMovement.objects.filter(created_by=staff_member).update(created_by=None)
            
            staff_member.delete()
            
            return JsonResponse({'success': True, 'message': f'Staff member "{username}" deleted successfully!'})
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})