# staff/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from inventoryApp.models import User

class StaffRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    phone = forms.CharField(max_length=15, required=False)
    role = forms.ChoiceField(choices=User.ROLE_CHOICES)
    branch = forms.ModelChoiceField(queryset=None, required=False)
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'phone', 'role', 'branch', 'password1', 'password2']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from branches.models import Branch
        self.fields['branch'].queryset = Branch.objects.filter(is_active=True).order_by('name')