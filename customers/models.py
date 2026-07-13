from django.db import models
from django.utils import timezone

class Customer(models.Model):
    CUSTOMER_TYPE = [
        ('regular', 'Regular'),
        ('vip', 'VIP'),
        ('wholesale', 'Wholesale'),
    ]
    
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=15, unique=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True)
    customer_type = models.CharField(max_length=20, choices=CUSTOMER_TYPE, default='regular')
    loyalty_points = models.IntegerField(default=0)
    total_purchases = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    last_purchase_date = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    branch = models.ForeignKey('branches.Branch', on_delete=models.SET_NULL, null=True, blank=True, related_name='customers')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'customers'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['phone']),
            models.Index(fields=['customer_type']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.phone})"
    
    def update_purchase_stats(self, amount):
        self.total_purchases += amount
        self.last_purchase_date = timezone.now()
        self.loyalty_points += int(amount / 10)
        self.save()