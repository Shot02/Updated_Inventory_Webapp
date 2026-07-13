from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
from inventoryApp.models import User
from sales.models import Sale, SaleItem

class RefundRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('declined', 'Declined'),
    ]
    
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, null=True, blank=True, related_name='refund_requests')
    sale_item = models.ForeignKey(SaleItem, on_delete=models.SET_NULL, null=True, blank=True)
    customer_name = models.CharField(max_length=200)
    customer_phone = models.CharField(max_length=15)
    reason = models.TextField()
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    original_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    request_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('declined', 'Declined'),
    ], default='pending')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_refunds')
    approved_date = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_refunds')
    refund_processed = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'refund_requests'
        ordering = ['-request_date']
    
    def __str__(self):
        return f"Refund #{self.id} - {self.customer_name} - ₦{self.amount}"
    
    def can_edit(self):
        return self.status == 'pending'
    
    def can_approve_decline(self, user):
        return self.status == 'pending' and (user.role == 'admin' or user.is_superuser)
    
    def get_related_sales(self):
        return Sale.objects.filter(
            Q(customer_name__iexact=self.customer_name) |
            Q(customer_phone__iexact=self.customer_phone)
        ).order_by('-created_at')


class Refund(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.SET_NULL, null=True, blank=True, related_name='refunds')
    refund_request = models.OneToOneField(RefundRequest, on_delete=models.CASCADE, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    reason = models.TextField()
    payment_method = models.CharField(max_length=50, choices=[
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('transfer', 'Bank Transfer'),
        ('refund', 'Refund Adjustment'),
    ], default='cash')
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    processed_date = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'refunds'
        ordering = ['-processed_date']
    
    def __str__(self):
        sale_ref = self.sale.invoice_number if self.sale else "No Sale"
        return f"Refund #{self.id} - {sale_ref} - ₦{self.amount}"
    
    def get_customer_name(self):
        if self.sale and self.sale.customer_name:
            return self.sale.customer_name
        elif self.refund_request:
            return self.refund_request.customer_name
        return "Unknown Customer"
    
    def save(self, *args, **kwargs):
        from inventoryApp.utils import safe_decimal
        self.amount = safe_decimal(self.amount)
        if self.amount < Decimal('0'):
            self.amount = Decimal('0')
        super().save(*args, **kwargs)
    
    def get_linked_sale(self):
        if self.sale:
            return self.sale
        elif self.refund_request and self.refund_request.sale:
            return self.refund_request.sale
        return None