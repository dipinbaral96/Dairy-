from decimal import Decimal
from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class Role(models.TextChoices):
    ADMIN = 'ADMIN', 'Admin'
    SELLER = 'SELLER', 'Seller'
    CUSTOMER = 'CUSTOMER', 'Customer'


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)
    phone = models.CharField(max_length=30, blank=True)
    address = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f'{self.user.username} - {self.get_role_display()}'


class DairyProfile(models.Model):
    name = models.CharField(max_length=150, default='Reliable Dairy')
    address = models.CharField(max_length=255, blank=True)
    pan_number = models.CharField(max_length=50, blank=True)
    contact_number = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    logo_url = models.URLField(blank=True, help_text='Optional URL/path to logo')
    bill_header = models.CharField(max_length=255, blank=True)
    bill_footer = models.CharField(max_length=255, blank=True)
    terms_conditions = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Shop(models.Model):
    name = models.CharField(max_length=120, unique=True)
    address = models.CharField(max_length=255, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Unit(models.Model):
    name = models.CharField(max_length=50, unique=True)
    short_form = models.CharField(max_length=20)
    used_for = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.short_form})'


class Product(models.Model):
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=30, unique=True)
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    category = models.CharField(max_length=80, blank=True)
    low_stock_threshold = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('5.00'))
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        self.code = (self.code or self.name[:5]).upper().replace(' ', '')
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.name} ({self.code})'

    @property
    def current_stock(self):
        total = self.batches.aggregate(total=models.Sum('available_quantity'))['total']
        return total or Decimal('0.00')


class ProductBatch(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = 'AVAILABLE', 'Available'
        SOLD = 'SOLD', 'Sold'
        EXPIRED = 'EXPIRED', 'Expired'

    batch_number = models.CharField(max_length=80, unique=True, editable=False)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='batches')
    received_date = models.DateField(default=timezone.localdate)
    quantity_received = models.DecimalField(max_digits=12, decimal_places=2)
    available_quantity = models.DecimalField(max_digits=12, decimal_places=2)
    expiry_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-received_date', 'product__name']

    def save(self, *args, **kwargs):
        if not self.batch_number:
            self.batch_number = generate_batch_number(self.product, self.received_date)
        if self.available_quantity is None:
            self.available_quantity = self.quantity_received
        if self.available_quantity <= 0:
            self.status = self.Status.SOLD
        elif self.expiry_date and self.expiry_date < timezone.localdate():
            self.status = self.Status.EXPIRED
        else:
            self.status = self.Status.AVAILABLE
        super().save(*args, **kwargs)

    def __str__(self):
        return self.batch_number


def generate_batch_number(product, received_date):
    date_str = received_date.strftime('%Y%m%d')
    prefix = product.code.upper()
    existing = ProductBatch.objects.filter(product=product, received_date=received_date).count() + 1
    return f'{prefix}-{date_str}-{existing:03d}'


class StockTransaction(models.Model):
    class Type(models.TextChoices):
        IN = 'IN', 'Stock In'
        OUT = 'OUT', 'Stock Out'
        ADJUST = 'ADJUST', 'Adjustment'

    transaction_type = models.CharField(max_length=10, choices=Type.choices)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    batch = models.ForeignKey(ProductBatch, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.transaction_type} {self.quantity} {self.product}'


class Customer(models.Model):
    class Type(models.TextChoices):
        REGULAR = 'REGULAR', 'Regular'
        WALK_IN = 'WALK_IN', 'Walk-in'

    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        INACTIVE = 'INACTIVE', 'Inactive'

    user = models.OneToOneField(User, on_delete=models.SET_NULL, blank=True, null=True, related_name='customer_record')
    name = models.CharField(max_length=150)
    mobile_number = models.CharField(max_length=30, unique=True)
    address = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    customer_type = models.CharField(max_length=20, choices=Type.choices, default=Type.REGULAR)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.mobile_number})'


class Seller(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='seller_record')
    shop = models.ForeignKey(Shop, on_delete=models.SET_NULL, null=True, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class PaymentMethod(models.Model):
    name = models.CharField(max_length=80, unique=True)
    active = models.BooleanField(default=True)
    payment_image = models.FileField(upload_to='payment_methods/', blank=True, help_text='Optional QR/payment image shown on invoice top-right.')

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class BillTemplate(models.Model):
    name = models.CharField(max_length=100, default='Default Bill')
    header_text = models.CharField(max_length=255, blank=True)
    footer_text = models.CharField(max_length=255, blank=True)
    show_pan = models.BooleanField(default=True)
    show_terms = models.BooleanField(default=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class FiscalYear(models.Model):
    """Nepali fiscal year setup used for invoice numbering, e.g. 2082-83."""
    name = models.CharField(max_length=40, unique=True, help_text='Example: 2082-83')
    start_date = models.DateField(help_text='Fiscal year start date in English/AD calendar.')
    end_date = models.DateField(help_text='Fiscal year end date in English/AD calendar.')
    invoice_prefix = models.CharField(max_length=30, default='INV', help_text='Example: INV, RD, BILL')
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return self.name

    @classmethod
    def current(cls, date=None):
        date = date or timezone.localdate()
        obj = cls.objects.filter(active=True, start_date__lte=date, end_date__gte=date).first()
        if obj:
            return obj
        obj = cls.objects.filter(active=True).order_by('-start_date').first()
        if obj:
            return obj
        return cls.objects.create(
            name=default_nepali_fiscal_year_code(date),
            start_date=timezone.datetime(date.year, 7, 16).date() if date.month >= 7 else timezone.datetime(date.year - 1, 7, 16).date(),
            end_date=timezone.datetime(date.year + 1, 7, 15).date() if date.month >= 7 else timezone.datetime(date.year, 7, 15).date(),
            invoice_prefix='INV',
            active=True,
        )


def default_nepali_fiscal_year_code(date):
    # Approximate Nepali fiscal year code without external dependency.
    # Around mid-July starts a new Nepali FY.
    if date.month > 7 or (date.month == 7 and date.day >= 16):
        start_np = date.year + 57
    else:
        start_np = date.year + 56
    return f'{start_np}-{str(start_np + 1)[-2:]}'


class Sale(models.Model):
    class Status(models.TextChoices):
        PAID = 'PAID', 'Paid'
        DUE = 'DUE', 'Due'
        CANCELLED = 'CANCELLED', 'Cancelled'

    bill_number = models.CharField(max_length=80, unique=True, editable=False)
    fiscal_year = models.ForeignKey(FiscalYear, on_delete=models.PROTECT, blank=True, null=True)
    invoice_sequence = models.PositiveIntegerField(default=0, editable=False)
    is_monthly_bill = models.BooleanField(default=False)
    billing_period_start = models.DateField(blank=True, null=True)
    billing_period_end = models.DateField(blank=True, null=True)
    seller = models.ForeignKey(User, on_delete=models.PROTECT, related_name='sales')
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='sales')
    shop = models.ForeignKey(Shop, on_delete=models.SET_NULL, blank=True, null=True)
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.PROTECT)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    due_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PAID)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.bill_number:
            self.fiscal_year = self.fiscal_year or FiscalYear.current(timezone.localdate())
            self.bill_number, self.invoice_sequence = generate_bill_number(self.fiscal_year)
        super().save(*args, **kwargs)

    @property
    def return_amount(self):
        """Amount to return to the customer when paid amount is greater than total."""
        return max((self.paid_amount or Decimal('0.00')) - (self.total_amount or Decimal('0.00')), Decimal('0.00'))

    def __str__(self):
        return self.bill_number


def generate_bill_number(fiscal_year=None):
    fiscal_year = fiscal_year or FiscalYear.current(timezone.localdate())
    existing = Sale.objects.filter(fiscal_year=fiscal_year).count() + 1
    prefix = fiscal_year.invoice_prefix or 'INV'
    return f'{prefix}-{fiscal_year.name}-{existing:04d}', existing


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    batch = models.ForeignKey(ProductBatch, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    rate = models.DecimalField(max_digits=12, decimal_places=2)
    item_discount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f'{self.product} - {self.quantity}'


class DailyCustomerProductEntry(models.Model):
    """Daily product supplied to a regular customer, later grouped into a monthly bill."""
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='daily_entries')
    entry_date = models.DateField(default=timezone.localdate)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    batch = models.ForeignKey(ProductBatch, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    rate = models.DecimalField(max_digits=12, decimal_places=2)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    seller = models.ForeignKey(User, on_delete=models.PROTECT, related_name='daily_customer_entries')
    shop = models.ForeignKey(Shop, on_delete=models.SET_NULL, blank=True, null=True)
    notes = models.CharField(max_length=255, blank=True)
    billed = models.BooleanField(default=False)
    sale = models.ForeignKey(Sale, on_delete=models.SET_NULL, blank=True, null=True, related_name='daily_entries')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-entry_date', '-created_at']

    def save(self, *args, **kwargs):
        if not self.rate and self.product_id:
            self.rate = self.product.selling_price
        self.amount = (self.quantity or Decimal('0.00')) * (self.rate or Decimal('0.00'))
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.customer.name} - {self.product.name} - {self.entry_date}'


class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    action = models.CharField(max_length=100)
    model_name = models.CharField(max_length=100)
    object_repr = models.CharField(max_length=255)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.created_at:%Y-%m-%d %H:%M} {self.action} {self.model_name}'


def _new_token_key():
    import secrets
    return secrets.token_hex(24)


class MobileAuthToken(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='mobile_token')
    key = models.CharField(max_length=96, unique=True, default=_new_token_key)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def rotate(self):
        self.key = _new_token_key()
        self.save(update_fields=['key', 'updated_at'])
        return self.key

    def __str__(self):
        return f'Token for {self.user.username}'


class NotificationLog(models.Model):
    class Channel(models.TextChoices):
        WEB = 'WEB', 'Web/App'
        EMAIL = 'EMAIL', 'Email'
        SMS = 'SMS', 'SMS'
        FIREBASE = 'FIREBASE', 'Firebase'

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        SENT = 'SENT', 'Sent'
        READ = 'READ', 'Read'
        FAILED = 'FAILED', 'Failed'

    title = models.CharField(max_length=180)
    message = models.TextField()
    recipient = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name='notifications')
    target_role = models.CharField(max_length=20, choices=Role.choices, blank=True)
    channel = models.CharField(max_length=20, choices=Channel.choices, default=Channel.WEB)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SENT)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name='created_notifications')
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def mark_read(self):
        self.status = self.Status.READ
        self.read_at = timezone.now()
        self.save(update_fields=['status', 'read_at'])

    def __str__(self):
        return self.title


class SavedReportConfig(models.Model):
    name = models.CharField(max_length=120)
    report_type = models.CharField(max_length=80)
    filters = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.report_type})'


class SystemSetting(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.CharField(max_length=255, blank=True)
    description = models.CharField(max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['key']

    def __str__(self):
        return self.key
