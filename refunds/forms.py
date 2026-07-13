# refunds/forms.py
from django import forms
from .models import RefundRequest

class RefundRequestForm(forms.ModelForm):
    class Meta:
        model = RefundRequest
        fields = ['customer_name', 'customer_phone', 'reason', 'amount']
        widgets = {
            'customer_name': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Enter customer name'
            }),
            'customer_phone': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Enter customer phone'
            }),
            'reason': forms.Textarea(attrs={
                'class': 'form-control', 
                'placeholder': 'Enter reason for refund', 
                'rows': 4
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Enter refund amount', 
                'step': '0.01', 
                'min': '0'
            }),
        }
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount <= 0:
            raise forms.ValidationError('Amount must be greater than zero.')
        return amount