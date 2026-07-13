from decimal import Decimal, ROUND_HALF_UP

def safe_decimal(value, default='0.00'):
    """
    Safely convert any value to Decimal with proper rounding.
    This fixes the negative profit issues and ensures all calculations
    are accurate.
    """
    try:
        if value is None:
            return Decimal(default).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if isinstance(value, Decimal):
            return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

def get_branch_filtered_queryset(request, queryset):
    """Filter queryset by current branch"""
    if request.user.is_superuser:
        return queryset
    current_branch = request.user.branch
    if current_branch:
        return queryset.filter(branch=current_branch)
    return queryset.none()