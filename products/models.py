from django.db import models
import uuid

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'categories'
        verbose_name_plural = 'Categories'
    
    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=200, default='Unnamed Product')
    sku = models.CharField(max_length=50, unique=True, editable=False, blank=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    supplier = models.ForeignKey('suppliers.Supplier', on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    quantity = models.IntegerField(default=0)
    reorder_level = models.IntegerField(default=10)
    branch = models.ForeignKey('branches.Branch', on_delete=models.CASCADE, null=True, blank=True, related_name='products')
    expiry_date = models.DateField(null=True, blank=True, help_text="Product expiry date")
    manufacturing_date = models.DateField(null=True, blank=True, help_text="Date of manufacture")
    batch_number = models.CharField(max_length=50, blank=True, null=True, help_text="Batch/Lot number")
    location = models.CharField(max_length=100, blank=True, null=True, help_text="Shelf/Storage location")
    is_active = models.BooleanField(default=True)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'products'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['expiry_date']),
            models.Index(fields=['supplier']),
            models.Index(fields=['name']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.sku})"
    
    def save(self, *args, **kwargs):
        if not self.sku:
            self.sku = f"PRD-{uuid.uuid4().hex[:6].upper()}"
            while Product.objects.filter(sku=self.sku).exists():
                self.sku = f"PRD-{uuid.uuid4().hex[:6].upper()}"
        
        if not self.name or self.name.strip() == '':
            self.name = 'Unnamed Product'
        
        if self.cost_price > self.price:
            self.cost_price = self.price
            
        super().save(*args, **kwargs)
    
    @property
    def is_low_stock(self):
        return self.quantity <= self.reorder_level
    
    @property
    def stock_status(self):
        if self.quantity == 0:
            return 'out_of_stock'
        elif self.quantity <= self.reorder_level:
            return 'low_stock'
        else:
            return 'in_stock'
    
    @property
    def expiry_status(self):
        from django.utils import timezone
        
        if not self.expiry_date:
            return 'no_expiry'
        
        today = timezone.now().date()
        days_until_expiry = (self.expiry_date - today).days
        
        if days_until_expiry < 0:
            return 'expired'
        elif days_until_expiry <= 30:
            return 'expiring_soon'
        elif days_until_expiry <= 90:
            return 'expiring'
        else:
            return 'valid'
    
    @property
    def days_until_expiry(self):
        from django.utils import timezone
        if not self.expiry_date:
            return None
        today = timezone.now().date()
        return (self.expiry_date - today).days