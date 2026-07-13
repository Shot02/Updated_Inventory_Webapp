from django.db import models
from decimal import Decimal
from django.db.models import F, Sum

class Supplier(models.Model):
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=15)
    address = models.TextField(blank=True)
    website = models.URLField(blank=True, null=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'suppliers'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    @property
    def total_products(self):
        return self.product_set.count()
    
    @property
    def total_products_sold(self):
        from sales.models import SaleItem
        total = SaleItem.objects.filter(
            product__supplier=self
        ).aggregate(total=Sum('quantity'))['total'] or 0
        return total
    
    @property
    def total_sales_amount(self):
        from sales.models import SaleItem
        total = SaleItem.objects.filter(
            product__supplier=self
        ).aggregate(total=Sum('total'))['total'] or Decimal('0.00')
        return total
    
    @property
    def total_profit(self):
        from sales.models import SaleItem
        from inventoryApp.utils import safe_decimal
        
        sale_items = SaleItem.objects.filter(product__supplier=self).select_related('product')
        total_profit = Decimal('0.00')
        
        for item in sale_items:
            if item.product:
                item_revenue = safe_decimal(item.total)
                item_cost = safe_decimal(item.product.cost_price) * Decimal(str(item.quantity))
                profit = item_revenue - item_cost
                total_profit += profit
        
        return total_profit
    
    @property
    def low_stock_products(self):
        return self.product_set.filter(quantity__lte=F('reorder_level'))
    
    @property
    def out_of_stock_products(self):
        return self.product_set.filter(quantity=0)