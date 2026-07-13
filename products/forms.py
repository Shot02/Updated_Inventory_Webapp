from django import forms
from .models import Product, Category
from suppliers.models import Supplier

class ProductForm(forms.ModelForm):
    new_category = forms.CharField(max_length=200, required=False, 
                                    widget=forms.TextInput(attrs={'placeholder': 'Or create new category'}))
    new_supplier = forms.CharField(max_length=200, required=False,
                                   widget=forms.TextInput(attrs={'placeholder': 'Or create new supplier'}))
    class Meta:
        model = Product
        fields = ['name', 'category', 'supplier', 'description', 'price', 
                  'cost_price', 'quantity', 'reorder_level', 'image']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-control'}),
            'supplier': forms.Select(attrs={'class': 'form-control'}),
        }
    def clean(self):
        cleaned_data = super().clean()
        
        if cleaned_data.get('new_category'):
            category, created = Category.objects.get_or_create(
                name=cleaned_data['new_category']
            )
            cleaned_data['category'] = category
        
        if cleaned_data.get('new_supplier'):
            supplier, created = Supplier.objects.get_or_create(
                name=cleaned_data['new_supplier']
            )
            cleaned_data['supplier'] = supplier
        
        return cleaned_data
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['price'].widget.attrs.update({'min': '0', 'step': '0.01'})
        self.fields['cost_price'].widget.attrs.update({'min': '0', 'step': '0.01'})
        self.fields['quantity'].widget.attrs.update({'min': '0'})
        self.fields['reorder_level'].widget.attrs.update({'min': '0'})
        self.fields['category'].required = False
        self.fields['supplier'].required = False