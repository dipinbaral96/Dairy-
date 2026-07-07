from decimal import Decimal
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.forms import formset_factory
from .models import (
    Customer, DairyProfile, PaymentMethod, Product, ProductBatch, Role, Sale,
    Seller, Shop, Unit, FiscalYear, DailyCustomerProductEntry
)


BOOTSTRAP_CLASS = 'form-control'


class BootstrapModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault('class', 'form-check-input')
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault('class', 'form-select')
            else:
                widget.attrs.setdefault('class', BOOTSTRAP_CLASS)


class DairyProfileForm(BootstrapModelForm):
    class Meta:
        model = DairyProfile
        fields = ['name', 'address', 'pan_number', 'contact_number', 'email', 'logo_url', 'bill_header', 'bill_footer', 'terms_conditions']
        widgets = {'terms_conditions': forms.Textarea(attrs={'rows': 3})}


class ShopForm(BootstrapModelForm):
    class Meta:
        model = Shop
        fields = ['name', 'address', 'active']


class UnitForm(BootstrapModelForm):
    class Meta:
        model = Unit
        fields = ['name', 'short_form', 'used_for']


class ProductForm(BootstrapModelForm):
    class Meta:
        model = Product
        fields = ['name', 'code', 'unit', 'selling_price', 'cost_price', 'category', 'low_stock_threshold', 'active']


class ProductReceivingForm(BootstrapModelForm):
    class Meta:
        model = ProductBatch
        fields = ['product', 'received_date', 'quantity_received', 'expiry_date']
        widgets = {
            'received_date': forms.DateInput(attrs={'type': 'date'}),
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean_quantity_received(self):
        qty = self.cleaned_data['quantity_received']
        if qty <= 0:
            raise forms.ValidationError('Quantity must be greater than zero.')
        return qty


class CustomerForm(BootstrapModelForm):
    class Meta:
        model = Customer
        fields = ['name', 'mobile_number', 'address', 'email', 'customer_type', 'status']

    create_login = forms.BooleanField(required=False, label='Create customer login account')
    username = forms.CharField(max_length=150, required=False, help_text='Required only when creating login.')
    password = forms.CharField(widget=forms.PasswordInput, required=False, help_text='Required only when creating login. Minimum 8 chars with letter, number, and symbol.')

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('create_login') and not self.instance.user:
            username = cleaned.get('username')
            password = cleaned.get('password')
            if not username:
                self.add_error('username', 'Username is required to create customer login.')
            elif User.objects.filter(username=username).exists():
                self.add_error('username', 'Username already exists.')
            if not password:
                self.add_error('password', 'Password is required to create customer login.')
            else:
                try:
                    validate_password(password)
                except forms.ValidationError as exc:
                    self.add_error('password', exc)
        return cleaned

    def save(self, commit=True):
        customer = super().save(commit=False)
        if commit:
            customer.save()
        if self.cleaned_data.get('create_login') and not customer.user:
            user = User.objects.create_user(
                username=self.cleaned_data['username'],
                password=self.cleaned_data['password'],
                email=customer.email,
                first_name=customer.name.split()[0] if customer.name else '',
                last_name=' '.join(customer.name.split()[1:]) if len(customer.name.split()) > 1 else '',
            )
            user.profile.role = Role.CUSTOMER
            user.profile.phone = customer.mobile_number
            user.profile.address = customer.address
            user.profile.save()
            customer.user = user
            if commit:
                customer.save(update_fields=['user'])
        return customer


class PaymentMethodForm(BootstrapModelForm):
    class Meta:
        model = PaymentMethod
        fields = ['name', 'active', 'payment_image']


class UserCreateForm(forms.Form):
    username = forms.CharField(max_length=150)
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=False)
    password = forms.CharField(widget=forms.PasswordInput, help_text='Minimum 8 chars with letter, number, and symbol.')
    role = forms.ChoiceField(choices=Role.choices)
    phone = forms.CharField(max_length=30, required=False)
    address = forms.CharField(max_length=255, required=False)
    shop = forms.ModelChoiceField(queryset=Shop.objects.filter(active=True), required=False, help_text='Required for seller account.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Username already exists.')
        return username

    def clean_password(self):
        password = self.cleaned_data['password']
        validate_password(password)
        return password

    def save(self):
        data = self.cleaned_data
        user = User.objects.create_user(
            username=data['username'],
            password=data['password'],
            email=data.get('email', ''),
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
        )
        user.profile.role = data['role']
        user.profile.phone = data.get('phone', '')
        user.profile.address = data.get('address', '')
        user.profile.save()
        if data['role'] == Role.ADMIN:
            user.is_staff = True
            user.save(update_fields=['is_staff'])
        if data['role'] == Role.SELLER:
            Seller.objects.update_or_create(user=user, defaults={'shop': data.get('shop'), 'phone': data.get('phone', ''), 'active': True})
        if data['role'] == Role.CUSTOMER and data.get('phone'):
            Customer.objects.get_or_create(
                mobile_number=data['phone'],
                defaults={'name': user.get_full_name() or user.username, 'email': user.email, 'address': data.get('address', ''), 'user': user}
            )
        return user


class UserEditForm(forms.ModelForm):
    role = forms.ChoiceField(choices=Role.choices)
    phone = forms.CharField(max_length=30, required=False)
    address = forms.CharField(max_length=255, required=False)
    shop = forms.ModelChoiceField(queryset=Shop.objects.filter(active=True), required=False)
    is_active = forms.BooleanField(required=False)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        profile = getattr(self.instance, 'profile', None)
        seller = getattr(self.instance, 'seller_record', None)
        if profile:
            self.fields['role'].initial = profile.role
            self.fields['phone'].initial = profile.phone
            self.fields['address'].initial = profile.address
        if seller:
            self.fields['shop'].initial = seller.shop
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'

    def save(self, commit=True):
        user = super().save(commit=commit)
        user.profile.role = self.cleaned_data['role']
        user.profile.phone = self.cleaned_data.get('phone', '')
        user.profile.address = self.cleaned_data.get('address', '')
        user.profile.save()
        if self.cleaned_data['role'] == Role.SELLER:
            Seller.objects.update_or_create(
                user=user,
                defaults={'shop': self.cleaned_data.get('shop'), 'phone': self.cleaned_data.get('phone', ''), 'active': user.is_active}
            )
        else:
            Seller.objects.filter(user=user).delete()
        return user


class SaleForm(BootstrapModelForm):
    class Meta:
        model = Sale
        fields = ['customer', 'shop', 'payment_method', 'discount', 'paid_amount']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['payment_method'].queryset = PaymentMethod.objects.filter(active=True)
        self.fields['shop'].queryset = Shop.objects.filter(active=True)
        self.fields['customer'].queryset = Customer.objects.filter(status=Customer.Status.ACTIVE)
        self.fields['discount'].initial = Decimal('0.00')
        self.fields['paid_amount'].initial = Decimal('0.00')
        if self.user and hasattr(self.user, 'seller_record') and self.user.seller_record.shop:
            self.fields['shop'].initial = self.user.seller_record.shop


class SaleItemForm(forms.Form):
    batch = forms.ModelChoiceField(queryset=ProductBatch.objects.none())
    quantity = forms.DecimalField(min_value=Decimal('0.01'), max_digits=12, decimal_places=2)
    item_discount = forms.DecimalField(min_value=Decimal('0.00'), max_digits=12, decimal_places=2, required=False, initial=Decimal('0.00'))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['batch'].queryset = ProductBatch.objects.filter(status=ProductBatch.Status.AVAILABLE, available_quantity__gt=0).select_related('product', 'product__unit').order_by('product__name', 'received_date')
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'


SaleItemFormSet = formset_factory(SaleItemForm, extra=5, can_delete=True)

from .models import BillTemplate, NotificationLog, SystemSetting
from django.contrib.auth.forms import PasswordChangeForm


class ProductBatchForm(BootstrapModelForm):
    class Meta:
        model = ProductBatch
        fields = ['product', 'received_date', 'quantity_received', 'available_quantity', 'expiry_date', 'status']
        widgets = {
            'received_date': forms.DateInput(attrs={'type': 'date'}),
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean(self):
        cleaned = super().clean()
        qty = cleaned.get('quantity_received')
        available = cleaned.get('available_quantity')
        if qty is not None and qty <= 0:
            self.add_error('quantity_received', 'Quantity received must be greater than zero.')
        if available is not None and available < 0:
            self.add_error('available_quantity', 'Available quantity cannot be negative.')
        if qty is not None and available is not None and available > qty:
            self.add_error('available_quantity', 'Available quantity cannot be greater than received quantity.')
        return cleaned


class BillTemplateForm(BootstrapModelForm):
    class Meta:
        model = BillTemplate
        fields = ['name', 'header_text', 'footer_text', 'show_pan', 'show_terms', 'active']


class NotificationForm(BootstrapModelForm):
    class Meta:
        model = NotificationLog
        fields = ['title', 'message', 'recipient', 'target_role', 'channel', 'status']
        widgets = {'message': forms.Textarea(attrs={'rows': 4})}

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('recipient') and not cleaned.get('target_role'):
            raise forms.ValidationError('Select either a recipient user or a target role.')
        return cleaned


class SystemSettingForm(BootstrapModelForm):
    class Meta:
        model = SystemSetting
        fields = ['key', 'value', 'description']


class CustomerProfileForm(BootstrapModelForm):
    class Meta:
        model = Customer
        fields = ['name', 'mobile_number', 'address', 'email']


class FiscalYearForm(BootstrapModelForm):
    class Meta:
        model = FiscalYear
        fields = ['name', 'start_date', 'end_date', 'invoice_prefix', 'active']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_date')
        end = cleaned.get('end_date')
        if start and end and end <= start:
            self.add_error('end_date', 'End date must be after start date.')
        return cleaned


class DailyCustomerProductEntryForm(BootstrapModelForm):
    class Meta:
        model = DailyCustomerProductEntry
        fields = ['customer', 'entry_date', 'batch', 'quantity', 'shop', 'notes']
        widgets = {'entry_date': forms.DateInput(attrs={'type': 'date'})}

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['customer'].queryset = Customer.objects.filter(status=Customer.Status.ACTIVE, customer_type=Customer.Type.REGULAR)
        self.fields['batch'].queryset = ProductBatch.objects.filter(status=ProductBatch.Status.AVAILABLE, available_quantity__gt=0).select_related('product', 'product__unit').order_by('product__name', 'received_date')
        self.fields['shop'].queryset = Shop.objects.filter(active=True)
        if self.user and hasattr(self.user, 'seller_record') and self.user.seller_record.shop:
            self.fields['shop'].initial = self.user.seller_record.shop

    def clean_quantity(self):
        qty = self.cleaned_data['quantity']
        if qty <= 0:
            raise forms.ValidationError('Quantity must be greater than zero.')
        return qty

    def clean(self):
        cleaned = super().clean()
        batch = cleaned.get('batch')
        qty = cleaned.get('quantity')
        if batch and qty and batch.available_quantity < qty:
            self.add_error('quantity', f'Not enough stock in batch {batch.batch_number}. Available: {batch.available_quantity}')
        return cleaned


class MonthlyBillForm(forms.Form):
    customer = forms.ModelChoiceField(queryset=Customer.objects.filter(status=Customer.Status.ACTIVE, customer_type=Customer.Type.REGULAR))
    period_start = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    period_end = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    payment_method = forms.ModelChoiceField(queryset=PaymentMethod.objects.filter(active=True))
    paid_amount = forms.DecimalField(min_value=Decimal('0.00'), max_digits=12, decimal_places=2, initial=Decimal('0.00'))
    discount = forms.DecimalField(min_value=Decimal('0.00'), max_digits=12, decimal_places=2, initial=Decimal('0.00'))
    shop = forms.ModelChoiceField(queryset=Shop.objects.filter(active=True), required=False)

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'
        if self.user and hasattr(self.user, 'seller_record') and self.user.seller_record.shop:
            self.fields['shop'].initial = self.user.seller_record.shop

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('period_start')
        end = cleaned.get('period_end')
        customer = cleaned.get('customer')
        if start and end and end < start:
            self.add_error('period_end', 'Period end must be after period start.')
        if customer and start and end:
            entries = DailyCustomerProductEntry.objects.filter(customer=customer, entry_date__gte=start, entry_date__lte=end, billed=False)
            if not entries.exists():
                raise forms.ValidationError('No unbilled daily product entries found for this customer and period.')
        return cleaned
