from decimal import Decimal
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import (
    BillTemplate, Customer, DairyProfile, MobileAuthToken, NotificationLog, PaymentMethod, Product, ProductBatch, Role, Seller,
    Shop, StockTransaction, SystemSetting, Unit, FiscalYear
)


class Command(BaseCommand):
    help = 'Seed demo data for the Dairy Management System.'

    def handle(self, *args, **options):
        profile = DairyProfile.get_solo()
        profile.name = profile.name or 'Reliable Dairy'
        profile.address = profile.address or 'Kathmandu, Nepal'
        profile.pan_number = profile.pan_number or '123456789'
        profile.contact_number = profile.contact_number or '98XXXXXXXX'
        profile.email = profile.email or 'info@reliabledairy.com'
        profile.bill_footer = profile.bill_footer or 'Thank you for buying from us.'
        profile.save()

        main_shop, _ = Shop.objects.get_or_create(name='Main Dairy Shop', defaults={'address': 'Kathmandu', 'active': True})
        Shop.objects.get_or_create(name='Bharatpur Branch', defaults={'address': 'Bharatpur, Chitwan', 'active': True})

        units = {
            'Litre': ('litre', 'Milk, curd'),
            'Kilogram': ('kg', 'Cheese, ghee, paneer'),
            'Gram': ('gm', 'Small packed products'),
            'Packet': ('pkt', 'Packaged items'),
            'Piece': ('pcs', 'Individual products'),
            'Millilitre': ('ml', 'Packaged milk, yogurt'),
        }
        unit_objs = {}
        for name, (short, used_for) in units.items():
            unit_objs[name], _ = Unit.objects.get_or_create(name=name, defaults={'short_form': short, 'used_for': used_for})

        products = [
            ('Milk', 'MILK', 'Litre', Decimal('120.00'), 'Liquid'),
            ('Curd', 'CURD', 'Litre', Decimal('150.00'), 'Liquid'),
            ('Ghee', 'GHEE', 'Kilogram', Decimal('1200.00'), 'Fat'),
            ('Paneer', 'PANEER', 'Kilogram', Decimal('700.00'), 'Solid'),
            ('Cheese', 'CHEESE', 'Kilogram', Decimal('900.00'), 'Solid'),
            ('Butter', 'BUTTER', 'Kilogram', Decimal('850.00'), 'Fat'),
        ]
        product_objs = []
        for name, code, unit_name, price, category in products:
            p, _ = Product.objects.get_or_create(
                code=code,
                defaults={'name': name, 'unit': unit_objs[unit_name], 'selling_price': price, 'category': category, 'low_stock_threshold': Decimal('5.00'), 'active': True},
            )
            product_objs.append(p)

        for method in ['Cash', 'eSewa', 'Khalti by IME', 'ConnectIPS', 'Mobile Banking', 'Bank Transfer', 'Credit / Due Payment']:
            PaymentMethod.objects.get_or_create(name=method, defaults={'active': True})


        # Default Nepali fiscal year for invoice number format such as INV-2082-83-0001.
        today = timezone.localdate()
        if today.month > 7 or (today.month == 7 and today.day >= 16):
            start_np = today.year + 57
            start_ad = timezone.datetime(today.year, 7, 16).date()
            end_ad = timezone.datetime(today.year + 1, 7, 15).date()
        else:
            start_np = today.year + 56
            start_ad = timezone.datetime(today.year - 1, 7, 16).date()
            end_ad = timezone.datetime(today.year, 7, 15).date()
        fy_name = f'{start_np}-{str(start_np + 1)[-2:]}'
        FiscalYear.objects.get_or_create(name=fy_name, defaults={'start_date': start_ad, 'end_date': end_ad, 'invoice_prefix': 'INV', 'active': True})

        BillTemplate.objects.get_or_create(
            name='Default Bill',
            defaults={'header_text': 'Official Dairy Invoice', 'footer_text': 'Thank you for buying fresh dairy products from us.', 'show_pan': True, 'show_terms': True, 'active': True},
        )
        default_settings = [
            ('site_language_default', 'en', 'Default website language'),
            ('mobile_api_enabled', 'true', 'Enable simple token-based mobile API'),
            ('seller_discount_allowed', 'true', 'Allow seller to apply bill/item discount'),
            ('low_stock_alert_enabled', 'true', 'Show low stock alerts on dashboard'),
        ]
        for key, value, description in default_settings:
            SystemSetting.objects.get_or_create(key=key, defaults={'value': value, 'description': description})

        admin, created = User.objects.get_or_create(username='admin', defaults={'email': 'admin@example.com', 'is_staff': True, 'is_superuser': True})
        if created:
            admin.set_password('Admin@12345')
            admin.save()
        admin.profile.role = Role.ADMIN
        admin.profile.save()

        seller, created = User.objects.get_or_create(username='seller1', defaults={'first_name': 'Demo', 'last_name': 'Seller', 'email': 'seller@example.com'})
        if created:
            seller.set_password('Seller@12345')
            seller.save()
        seller.profile.role = Role.SELLER
        seller.profile.phone = '9800000001'
        seller.profile.save()
        Seller.objects.update_or_create(user=seller, defaults={'shop': main_shop, 'phone': '9800000001', 'active': True})

        customer_user, created = User.objects.get_or_create(username='customer1', defaults={'first_name': 'Ram', 'last_name': 'Bahadur', 'email': 'customer@example.com'})
        if created:
            customer_user.set_password('Customer@12345')
            customer_user.save()
        customer_user.profile.role = Role.CUSTOMER
        customer_user.profile.phone = '9800000002'
        customer_user.profile.address = 'Chitwan'
        customer_user.profile.save()
        customer, _ = Customer.objects.update_or_create(
            mobile_number='9800000002',
            defaults={'name': 'Ram Bahadur', 'address': 'Chitwan', 'email': 'customer@example.com', 'user': customer_user},
        )

        for product in product_objs[:3]:
            if not ProductBatch.objects.filter(product=product, received_date=today).exists():
                qty = Decimal('100.00') if product.code == 'MILK' else Decimal('30.00')
                batch = ProductBatch.objects.create(product=product, received_date=today, quantity_received=qty, available_quantity=qty, created_by=admin)
                StockTransaction.objects.create(transaction_type=StockTransaction.Type.IN, product=product, batch=batch, quantity=qty, reason='Seed stock', created_by=admin)

        for user in [admin, seller, customer_user]:
            MobileAuthToken.objects.get_or_create(user=user)

        NotificationLog.objects.get_or_create(
            title='Welcome to Dairy Management System',
            target_role=Role.ADMIN,
            defaults={'message': 'System is ready with admin, seller, customer, product, billing, MIS, backup, and mobile API modules.', 'created_by': admin},
        )

        self.stdout.write(self.style.SUCCESS('Demo data is ready. Login: admin/Admin@12345, seller1/Seller@12345, customer1/Customer@12345'))
