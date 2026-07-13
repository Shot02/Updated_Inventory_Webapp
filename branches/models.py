from django.db import models

class Branch(models.Model):
    name = models.CharField(max_length=100, help_text="Branch name (e.g., Lagos Branch, Ibadan Branch)")
    code = models.CharField(max_length=20, unique=True, help_text="Branch code (e.g., LAG, IBA)")
    address = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    manager = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'branches'
        ordering = ['name']
        verbose_name = 'Branch'
        verbose_name_plural = 'Branches'
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    @property
    def staff_count(self):
        return self.users.filter(is_active=True).count()
    
    @property
    def product_count(self):
        return self.products.filter(is_active=True).count()
    
    @property
    def sales_count(self):
        return self.sales.count()