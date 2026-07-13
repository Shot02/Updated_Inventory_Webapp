from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
from inventoryApp.models import User
from products.models import Product
from branches.models import Branch

class Sale(models.Model):
    invoice_number = models.CharField(max_length=50, unique=True)
    staff = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    customer_name = models.CharField(max_length=200, blank=True)
    customer_phone = models.CharField(max_length=15, blank=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, null=True, blank=True, related_name='sales')
    payment_status = models.CharField(max_length=20, choices=[
        ('paid', 'Paid'),
        ('partial', 'Partial Payment'),
        ('unpaid', 'Unpaid')
    ], default='paid')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'sales'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Invoice {self.invoice_number}"
    
    def save(self, *args, **kwargs):
        # FIXED: Proper Decimal handling
        self.balance = Decimal(str(self.total)) - Decimal(str(self.amount_paid))
        if self.balance < Decimal('0'):
            self.balance = Decimal('0')
        
        if self.balance <= Decimal('0'):
            self.payment_status = 'paid'
        elif self.balance < self.total:
            self.payment_status = 'partial'
        else:
            self.payment_status = 'unpaid'
            
        super().save(*args, **kwargs)

class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    product_name = models.CharField(max_length=200)
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    
    class Meta:
        db_table = 'sale_items'

class Payment(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50, choices=[
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('transfer', 'Bank Transfer'),
    ], default='cash')
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        db_table = 'payments'
        ordering = ['-created_at']

class StockMovement(models.Model):
    MOVEMENT_TYPES = [
        ('in', 'Stock In'),
        ('out', 'Stock Out'),
        ('adjustment', 'Adjustment'),
    ]
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    quantity = models.IntegerField()
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'stock_movements'
        ordering = ['-created_at']

class PendingCart(models.Model):
    staff = models.ForeignKey(User, on_delete=models.CASCADE)
    cart_data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'pending_carts'
        unique_together = ['staff']

class SavedCart(models.Model):
    staff = models.ForeignKey(User, on_delete=models.CASCADE)
    cart_name = models.CharField(max_length=100, default="Unsaved Cart")
    cart_data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'saved_carts'
        ordering = ['-created_at']
    
    @property
    def items_count(self):
        if self.cart_data and 'items' in self.cart_data:
            return len(self.cart_data['items'])
        return 0
    
    @property
    def total_amount(self):
        if self.cart_data and 'items' in self.cart_data:
            total = sum(
                (item.get('price', 0) * item.get('quantity', 1)) - item.get('discount', 0)
                for item in self.cart_data['items']
            )
            return Decimal(str(total))
        return Decimal('0.00')