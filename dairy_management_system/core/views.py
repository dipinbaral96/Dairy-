from decimal import Decimal
from io import BytesIO
import csv
import json
import os
import shutil
from pathlib import Path
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.contrib.auth import authenticate, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.db import connection, transaction
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .decorators import admin_required, customer_required, get_role, role_required, seller_required
from .forms import (
    BillTemplateForm, CustomerForm, CustomerProfileForm, DairyProfileForm, NotificationForm,
    PaymentMethodForm, ProductBatchForm, ProductForm, ProductReceivingForm, SaleForm,
    SaleItemFormSet, ShopForm, SystemSettingForm, UnitForm, UserCreateForm, UserEditForm,
    PasswordChangeForm, FiscalYearForm, DailyCustomerProductEntryForm, MonthlyBillForm
)
from .models import (
    AuditLog, BillTemplate, Customer, DairyProfile, MobileAuthToken, NotificationLog,
    PaymentMethod, Product, ProductBatch, Role, Sale, SaleItem, SavedReportConfig, Seller,
    Shop, StockTransaction, SystemSetting, Unit, FiscalYear, DailyCustomerProductEntry
)
from .utils import create_sale_with_items, log_action
from django.db.models.functions import TruncDate, TruncMonth


class DairyLoginView(LoginView):
    template_name = 'core/login.html'


@login_required
def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('login')


@login_required
def dashboard(request):
    role = get_role(request.user)
    if role == Role.ADMIN:
        return redirect('admin_dashboard')
    if role == Role.SELLER:
        return redirect('seller_dashboard')
    return redirect('customer_dashboard')


@admin_required
def admin_dashboard(request):
    today = timezone.localdate()
    context = {
        'products_count': Product.objects.count(),
        'customers_count': Customer.objects.count(),
        'sellers_count': User.objects.filter(profile__role=Role.SELLER).count(),
        'today_sales': Sale.objects.filter(created_at__date=today).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00'),
        'low_stock_products': [p for p in Product.objects.filter(active=True).select_related('unit') if p.current_stock <= p.low_stock_threshold],
        'recent_sales': Sale.objects.select_related('customer', 'seller', 'payment_method').order_by('-created_at')[:8],
        'recent_logs': AuditLog.objects.select_related('user').order_by('-created_at')[:8],
    }
    return render(request, 'core/admin_dashboard.html', context)


@seller_required
def seller_dashboard(request):
    today = timezone.localdate()
    context = {
        'today_sales': Sale.objects.filter(seller=request.user, created_at__date=today).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00'),
        'available_batches': ProductBatch.objects.filter(status=ProductBatch.Status.AVAILABLE, available_quantity__gt=0).select_related('product')[:10],
        'recent_bills': Sale.objects.filter(seller=request.user).select_related('customer', 'payment_method').order_by('-created_at')[:8],
        'payment_summary': Sale.objects.filter(seller=request.user, created_at__date=today).values('payment_method__name').annotate(total=Sum('total_amount')).order_by('payment_method__name'),
    }
    return render(request, 'core/seller_dashboard.html', context)


@customer_required
def customer_dashboard(request):
    customer = Customer.objects.filter(user=request.user).first()
    if not customer and getattr(request.user, 'profile', None):
        customer = Customer.objects.filter(mobile_number=request.user.profile.phone).first()
    sales = Sale.objects.none()
    if customer:
        sales = Sale.objects.filter(customer=customer).select_related('payment_method').prefetch_related('items__product').order_by('-created_at')
    return render(request, 'core/customer_dashboard.html', {'customer': customer, 'sales': sales})


@admin_required
def dairy_profile(request):
    profile = DairyProfile.get_solo()
    if request.method == 'POST':
        form = DairyProfileForm(request.POST, instance=profile)
        if form.is_valid():
            obj = form.save()
            log_action(request.user, 'UPDATE', obj)
            messages.success(request, 'Dairy profile updated.')
            return redirect('dairy_profile')
    else:
        form = DairyProfileForm(instance=profile)
    return render(request, 'core/form.html', {'form': form, 'title': 'Dairy Profile Setup'})


@admin_required
def user_list(request):
    users = User.objects.select_related('profile').order_by('username')
    return render(request, 'core/user_list.html', {'users': users})


@admin_required
def user_create(request):
    if request.method == 'POST':
        form = UserCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
            log_action(request.user, 'CREATE', user, 'User account created')
            messages.success(request, 'User created successfully.')
            return redirect('user_list')
    else:
        form = UserCreateForm()
    return render(request, 'core/form.html', {'form': form, 'title': 'Add User'})


@admin_required
def user_update(request, pk):
    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            log_action(request.user, 'UPDATE', user, 'User account updated')
            messages.success(request, 'User updated successfully.')
            return redirect('user_list')
    else:
        form = UserEditForm(instance=user)
    return render(request, 'core/form.html', {'form': form, 'title': 'Edit User'})


@admin_required
@require_POST
def user_delete(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user == request.user:
        messages.error(request, 'You cannot delete your own account while logged in.')
    else:
        log_action(request.user, 'DELETE', user, 'User account deleted')
        user.delete()
        messages.success(request, 'User deleted.')
    return redirect('user_list')


def generic_list_create_update_delete(request, model, form_class, template, title, pk=None, delete=False):
    obj = get_object_or_404(model, pk=pk) if pk else None
    if delete:
        try:
            log_action(request.user, 'DELETE', obj)
            obj.delete()
            messages.success(request, f'{title} deleted.')
        except Exception as exc:
            messages.error(request, f'{title} could not be deleted: {exc}')
        return redirect(template + '_list')
    if request.method == 'POST':
        form = form_class(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            saved = form.save()
            log_action(request.user, 'UPDATE' if obj else 'CREATE', saved)
            messages.success(request, f'{title} saved successfully.')
            return redirect(template + '_list')
    else:
        form = form_class(instance=obj)
    return render(request, 'core/form.html', {'form': form, 'title': f'{"Edit" if obj else "Add"} {title}'})


@admin_required
def shop_list(request):
    return render(request, 'core/simple_list.html', {'title': 'Shops / Branches', 'items': Shop.objects.all(), 'columns': ['name', 'address', 'active'], 'add_url': 'shop_create', 'edit_url': 'shop_update', 'delete_url': 'shop_delete'})

@admin_required
def shop_create(request):
    return generic_list_create_update_delete(request, Shop, ShopForm, 'shop', 'Shop')

@admin_required
def shop_update(request, pk):
    return generic_list_create_update_delete(request, Shop, ShopForm, 'shop', 'Shop', pk=pk)

@admin_required
@require_POST
def shop_delete(request, pk):
    return generic_list_create_update_delete(request, Shop, ShopForm, 'shop', 'Shop', pk=pk, delete=True)


@admin_required
def unit_list(request):
    return render(request, 'core/simple_list.html', {'title': 'Units / Metric System', 'items': Unit.objects.all(), 'columns': ['name', 'short_form', 'used_for'], 'add_url': 'unit_create', 'edit_url': 'unit_update', 'delete_url': 'unit_delete'})

@admin_required
def unit_create(request):
    return generic_list_create_update_delete(request, Unit, UnitForm, 'unit', 'Unit')

@admin_required
def unit_update(request, pk):
    return generic_list_create_update_delete(request, Unit, UnitForm, 'unit', 'Unit', pk=pk)

@admin_required
@require_POST
def unit_delete(request, pk):
    return generic_list_create_update_delete(request, Unit, UnitForm, 'unit', 'Unit', pk=pk, delete=True)


@admin_required
def product_list(request):
    products = Product.objects.select_related('unit')
    return render(request, 'core/product_list.html', {'products': products})

@admin_required
def product_create(request):
    return generic_list_create_update_delete(request, Product, ProductForm, 'product', 'Product')

@admin_required
def product_update(request, pk):
    return generic_list_create_update_delete(request, Product, ProductForm, 'product', 'Product', pk=pk)

@admin_required
@require_POST
def product_delete(request, pk):
    return generic_list_create_update_delete(request, Product, ProductForm, 'product', 'Product', pk=pk, delete=True)


@seller_required
def customer_list(request):
    query = request.GET.get('q', '')
    customers = Customer.objects.all()
    if query:
        customers = customers.filter(name__icontains=query) | Customer.objects.filter(mobile_number__icontains=query)
    return render(request, 'core/customer_list.html', {'customers': customers, 'query': query})


@seller_required
def customer_create(request):
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save()
            log_action(request.user, 'CREATE', customer)
            messages.success(request, 'Customer saved successfully.')
            next_url = request.GET.get('next')
            return redirect(next_url or 'customer_list')
    else:
        form = CustomerForm()
    return render(request, 'core/form.html', {'form': form, 'title': 'Add Customer'})


@seller_required
def customer_update(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            obj = form.save()
            log_action(request.user, 'UPDATE', obj)
            messages.success(request, 'Customer updated successfully.')
            return redirect('customer_list')
    else:
        form = CustomerForm(instance=customer)
    return render(request, 'core/form.html', {'form': form, 'title': 'Edit Customer'})


@admin_required
@require_POST
def customer_delete(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    log_action(request.user, 'DELETE', customer)
    customer.delete()
    messages.success(request, 'Customer deleted.')
    return redirect('customer_list')


@admin_required
def payment_list(request):
    return render(request, 'core/simple_list.html', {'title': 'Payment Methods', 'items': PaymentMethod.objects.all(), 'columns': ['name', 'active', 'payment_image'], 'add_url': 'payment_create', 'edit_url': 'payment_update', 'delete_url': 'payment_delete'})

@admin_required
def payment_create(request):
    return generic_list_create_update_delete(request, PaymentMethod, PaymentMethodForm, 'payment', 'Payment Method')

@admin_required
def payment_update(request, pk):
    return generic_list_create_update_delete(request, PaymentMethod, PaymentMethodForm, 'payment', 'Payment Method', pk=pk)

@admin_required
@require_POST
def payment_delete(request, pk):
    return generic_list_create_update_delete(request, PaymentMethod, PaymentMethodForm, 'payment', 'Payment Method', pk=pk, delete=True)


@admin_required
def receiving_list(request):
    batches = ProductBatch.objects.select_related('product', 'product__unit').order_by('-received_date', '-created_at')
    return render(request, 'core/receiving_list.html', {'batches': batches})


@admin_required
def receiving_create(request):
    if request.method == 'POST':
        form = ProductReceivingForm(request.POST)
        if form.is_valid():
            batch = form.save(commit=False)
            batch.available_quantity = batch.quantity_received
            batch.created_by = request.user
            batch.save()
            StockTransaction.objects.create(
                transaction_type=StockTransaction.Type.IN,
                product=batch.product,
                batch=batch,
                quantity=batch.quantity_received,
                reason='Daily product receiving',
                created_by=request.user,
            )
            log_action(request.user, 'CREATE', batch, 'Daily product receiving')
            messages.success(request, f'Product received. Batch created: {batch.batch_number}')
            return redirect('receiving_list')
    else:
        form = ProductReceivingForm()
    return render(request, 'core/form.html', {'form': form, 'title': 'Daily Product Receiving'})


@seller_required
def batch_search(request):
    query = request.GET.get('q', '')
    batches = ProductBatch.objects.filter(status=ProductBatch.Status.AVAILABLE, available_quantity__gt=0).select_related('product', 'product__unit')
    if query:
        batches = batches.filter(batch_number__icontains=query) | ProductBatch.objects.filter(product__name__icontains=query, status=ProductBatch.Status.AVAILABLE, available_quantity__gt=0).select_related('product', 'product__unit')
    return render(request, 'core/batch_search.html', {'batches': batches, 'query': query})


@seller_required
def sale_create(request):
    if request.method == 'POST':
        form = SaleForm(request.POST, user=request.user)
        formset = SaleItemFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            try:
                sale = form.save(commit=False)
                create_sale_with_items(request.user, sale, formset.forms)
                messages.success(request, f'Bill generated successfully: {sale.bill_number}')
                return redirect('sale_detail', pk=sale.pk)
            except ValueError as exc:
                messages.error(request, str(exc))
    else:
        form = SaleForm(user=request.user)
        formset = SaleItemFormSet()
    return render(request, 'core/sale_form.html', {'form': form, 'formset': formset, 'title': 'Generate Bill'})


@seller_required
def sale_list(request):
    sales = Sale.objects.select_related('customer', 'seller', 'payment_method', 'shop').order_by('-created_at')
    if get_role(request.user) == Role.SELLER:
        sales = sales.filter(seller=request.user)
    return render(request, 'core/sale_list.html', {'sales': sales})


@login_required
def sale_detail(request, pk):
    sale = get_object_or_404(Sale.objects.select_related('customer', 'seller', 'payment_method', 'shop').prefetch_related('items__product', 'items__batch'), pk=pk)
    role = get_role(request.user)
    if role == Role.SELLER and sale.seller != request.user:
        messages.error(request, 'You can view only your own bills.')
        return redirect('sale_list')
    if role == Role.CUSTOMER:
        customer = Customer.objects.filter(user=request.user).first()
        if not customer and getattr(request.user, 'profile', None):
            customer = Customer.objects.filter(mobile_number=request.user.profile.phone).first()
        if not customer or sale.customer_id != customer.id:
            messages.error(request, 'You can view only your own bills.')
            return redirect('customer_dashboard')
    return render(request, 'core/sale_detail.html', {'sale': sale, 'bill_template': BillTemplate.objects.filter(active=True).first()})


@login_required
def sale_pdf(request, pk):
    sale = get_object_or_404(Sale.objects.select_related('customer', 'seller', 'payment_method', 'shop').prefetch_related('items__product', 'items__batch'), pk=pk)
    role = get_role(request.user)
    if role == Role.SELLER and sale.seller != request.user:
        messages.error(request, 'You can download only your own bills.')
        return redirect('sale_list')
    if role == Role.CUSTOMER:
        customer = Customer.objects.filter(user=request.user).first()
        if not customer and getattr(request.user, 'profile', None):
            customer = Customer.objects.filter(mobile_number=request.user.profile.phone).first()
        if not customer or sale.customer_id != customer.id:
            messages.error(request, 'You can download only your own bills.')
            return redirect('customer_dashboard')
    profile = DairyProfile.get_solo()
    bill_template = BillTemplate.objects.filter(active=True).first()
    header_text = (bill_template.header_text if bill_template and bill_template.header_text else profile.bill_header)
    footer_text = (bill_template.footer_text if bill_template and bill_template.footer_text else profile.bill_footer)
    buffer = BytesIO()
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfgen import canvas
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        y = height - 42

        logo_path = settings.BASE_DIR / 'static' / 'img' / 'mainlogo_square.png'
        if logo_path.exists():
            p.drawImage(ImageReader(str(logo_path)), 50, y - 54, width=54, height=54, preserveAspectRatio=True, mask='auto')
            text_x = 116
        else:
            text_x = 50
        if sale.payment_method.payment_image:
            try:
                pay_path = settings.BASE_DIR / sale.payment_method.payment_image.name
                if not pay_path.exists():
                    pay_path = settings.MEDIA_ROOT / sale.payment_method.payment_image.name
                if pay_path.exists():
                    p.setFont('Helvetica-Bold', 8)
                    p.drawRightString(width - 50, y - 6, f'{sale.payment_method.name} Payment')
                    p.drawImage(ImageReader(str(pay_path)), width - 130, y - 62, width=80, height=54, preserveAspectRatio=True, mask='auto')
            except Exception:
                pass

        p.setFillColor(colors.HexColor('#0f2f5f'))
        p.setFont('Helvetica-Bold', 18)
        p.drawString(text_x, y - 5, profile.name)
        p.setFillColor(colors.black)
        p.setFont('Helvetica', 9)
        p.drawString(text_x, y - 22, profile.address or '')
        p.drawString(text_x, y - 38, f'PAN: {profile.pan_number or "-"} | Contact: {profile.contact_number or "-"}')
        p.setStrokeColor(colors.HexColor('#e1262f'))
        p.setLineWidth(2)
        p.line(50, y - 66, width - 50, y - 66)
        y -= 92

        p.setFillColor(colors.HexColor('#0f2f5f'))
        p.setFont('Helvetica-Bold', 13)
        p.drawString(50, y, header_text or 'Invoice / Bill')
        p.setFillColor(colors.black)
        y -= 22
        p.setFont('Helvetica', 10)
        p.drawString(50, y, f'Invoice No: {sale.bill_number}')
        p.drawString(330, y, f'Date: {sale.created_at:%Y-%m-%d %H:%M}')
        y -= 16
        p.drawString(50, y, f'Customer: {sale.customer.name}')
        p.drawString(330, y, f'Seller: {sale.seller.get_full_name() or sale.seller.username}')
        y -= 16
        p.drawString(50, y, f'Mobile: {sale.customer.mobile_number}')
        p.drawString(330, y, f'Shop: {sale.shop.name if sale.shop else "-"}')
        if sale.is_monthly_bill and sale.billing_period_start and sale.billing_period_end:
            y -= 16
            p.drawString(50, y, f'Monthly Billing Period: {sale.billing_period_start} to {sale.billing_period_end}')
        y -= 30

        p.setFillColor(colors.HexColor('#0f2f5f'))
        p.rect(50, y - 4, width - 100, 22, fill=1, stroke=0)
        p.setFillColor(colors.white)
        p.setFont('Helvetica-Bold', 9)
        p.drawString(58, y + 2, 'Product')
        p.drawString(176, y + 2, 'Batch')
        p.drawString(328, y + 2, 'Qty')
        p.drawString(388, y + 2, 'Rate')
        p.drawString(456, y + 2, 'Amount')
        y -= 22
        p.setFillColor(colors.black)
        p.setFont('Helvetica', 9)
        for item in sale.items.all():
            p.drawString(58, y, item.product.name[:20])
            p.drawString(176, y, item.batch.batch_number[:24])
            p.drawRightString(360, y, str(item.quantity))
            p.drawRightString(430, y, str(item.rate))
            p.drawRightString(520, y, str(item.amount))
            y -= 18
            if y < 110:
                p.showPage(); y = height - 50

        y -= 12
        p.setStrokeColor(colors.HexColor('#d6deea'))
        p.line(330, y + 8, 525, y + 8)
        p.setFont('Helvetica-Bold', 10)
        p.drawRightString(450, y, 'Overall Discount:')
        p.drawRightString(525, y, f'Rs. {sale.discount}')
        y -= 18
        p.drawRightString(450, y, 'Paid:')
        p.drawRightString(525, y, f'Rs. {sale.paid_amount}')
        y -= 18
        p.drawRightString(450, y, 'Total:')
        p.drawRightString(525, y, f'Rs. {sale.total_amount}')
        y -= 18
        p.drawRightString(450, y, 'Return:')
        p.drawRightString(525, y, f'Rs. {sale.return_amount}')
        y -= 18
        p.drawRightString(450, y, 'Due:')
        p.drawRightString(525, y, f'Rs. {sale.due_amount}')
        y -= 28
        p.setFont('Helvetica', 9)
        p.drawString(50, y, f'Payment Method: {sale.payment_method.name} | Status: {sale.get_status_display()}')
        y -= 26
        p.setFillColor(colors.HexColor('#64748b'))
        p.drawString(50, y, footer_text or 'Thank you for your purchase.')
        p.showPage()
        p.save()
        buffer.seek(0)
        log_action(request.user, 'DOWNLOAD', sale, 'Bill PDF downloaded')
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{sale.bill_number}.pdf"'
        return response
    except Exception as exc:
        messages.error(request, f'PDF could not be generated: {exc}')
        return redirect('sale_detail', pk=sale.pk)


@role_required(Role.ADMIN, Role.SELLER)
def stock_report(request):
    products = Product.objects.filter(active=True).select_related('unit')
    rows = []
    for product in products:
        rows.append({'product': product, 'stock': product.current_stock, 'low': product.current_stock <= product.low_stock_threshold})
    return render(request, 'core/stock_report.html', {'rows': rows})


@role_required(Role.ADMIN, Role.SELLER)
def sales_report(request):
    sales = Sale.objects.select_related('customer', 'seller', 'shop', 'payment_method').prefetch_related('items__product')
    if get_role(request.user) == Role.SELLER:
        sales = sales.filter(seller=request.user)
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    shop = request.GET.get('shop')
    payment = request.GET.get('payment')
    customer = request.GET.get('customer')
    seller = request.GET.get('seller')

    if date_from:
        sales = sales.filter(created_at__date__gte=date_from)
    if date_to:
        sales = sales.filter(created_at__date__lte=date_to)
    if shop:
        sales = sales.filter(shop_id=shop)
    if payment:
        sales = sales.filter(payment_method_id=payment)
    if customer:
        sales = sales.filter(customer_id=customer)
    if seller:
        sales = sales.filter(seller_id=seller)

    total_sales = sales.aggregate(total=Sum('total_amount'), due=Sum('due_amount'))

    if request.GET.get('export') == 'excel':
        return export_sales_excel(sales)
    if request.GET.get('export') == 'pdf':
        return export_sales_pdf(sales, total_sales)

    context = {
        'sales': sales.order_by('-created_at'),
        'total_amount': total_sales['total'] or Decimal('0.00'),
        'total_due': total_sales['due'] or Decimal('0.00'),
        'shops': Shop.objects.filter(active=True),
        'payments': PaymentMethod.objects.filter(active=True),
        'customers': Customer.objects.all(),
        'sellers': User.objects.filter(pk=request.user.pk) if get_role(request.user) == Role.SELLER else User.objects.filter(profile__role=Role.SELLER),
        'filters': request.GET,
    }
    return render(request, 'core/sales_report.html', context)


def export_sales_excel(sales):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = 'Sales Report'
    ws.append(['Bill No', 'Date', 'Customer', 'Seller', 'Shop', 'Payment', 'Total', 'Paid', 'Due', 'Status'])
    for sale in sales.order_by('-created_at'):
        ws.append([
            sale.bill_number,
            sale.created_at.strftime('%Y-%m-%d %H:%M'),
            sale.customer.name,
            sale.seller.get_full_name() or sale.seller.username,
            sale.shop.name if sale.shop else '',
            sale.payment_method.name,
            float(sale.total_amount),
            float(sale.paid_amount),
            float(sale.due_amount),
            sale.status,
        ])
    buffer = BytesIO()
    wb.save(buffer)
    response = HttpResponse(buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="sales_report.xlsx"'
    return response


def export_sales_pdf(sales, total_sales):
    buffer = BytesIO()
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 50
    p.setFont('Helvetica-Bold', 16)
    p.drawString(50, y, 'Sales Report')
    y -= 25
    p.setFont('Helvetica', 9)
    p.drawString(50, y, f'Generated: {timezone.localtime():%Y-%m-%d %H:%M}')
    y -= 25
    p.setFont('Helvetica-Bold', 9)
    headers = [('Bill', 50), ('Date', 130), ('Customer', 230), ('Payment', 340), ('Total', 430), ('Due', 500)]
    for text, x in headers:
        p.drawString(x, y, text)
    y -= 15
    p.setFont('Helvetica', 8)
    for sale in sales.order_by('-created_at'):
        p.drawString(50, y, sale.bill_number[:13])
        p.drawString(130, y, sale.created_at.strftime('%Y-%m-%d'))
        p.drawString(230, y, sale.customer.name[:18])
        p.drawString(340, y, sale.payment_method.name[:12])
        p.drawString(430, y, str(sale.total_amount))
        p.drawString(500, y, str(sale.due_amount))
        y -= 14
        if y < 70:
            p.showPage(); y = height - 50
    y -= 20
    p.setFont('Helvetica-Bold', 10)
    p.drawString(50, y, f'Total Sales: Rs. {total_sales["total"] or Decimal("0.00")}')
    y -= 15
    p.drawString(50, y, f'Total Due: Rs. {total_sales["due"] or Decimal("0.00")}')
    p.showPage()
    p.save()
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="sales_report.pdf"'
    return response


@admin_required
def audit_logs(request):
    logs = AuditLog.objects.select_related('user').order_by('-created_at')
    action = request.GET.get('action', '').strip()
    model_name = request.GET.get('model', '').strip()
    user_query = request.GET.get('user', '').strip()
    q = request.GET.get('q', '').strip()

    if action:
        logs = logs.filter(action__icontains=action)
    if model_name:
        logs = logs.filter(model_name__icontains=model_name)
    if user_query:
        logs = logs.filter(user__username__icontains=user_query)
    if q:
        logs = logs.filter(Q(object_repr__icontains=q) | Q(notes__icontains=q))

    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="activity_logs.csv"'
        writer = csv.writer(response)
        writer.writerow(['Date', 'User', 'Action', 'Model', 'Object', 'Notes'])
        for log in logs[:5000]:
            writer.writerow([
                timezone.localtime(log.created_at).strftime('%Y-%m-%d %H:%M:%S'),
                log.user.username if log.user else 'System',
                log.action,
                log.model_name,
                log.object_repr,
                log.notes,
            ])
        return response

    return render(request, 'core/audit_logs.html', {'logs': logs[:300], 'filters': request.GET})


def _backup_dir():
    path = settings.BASE_DIR / 'backups'
    path.mkdir(exist_ok=True)
    return path


def _db_path():
    db_name = settings.DATABASES['default']['NAME']
    return Path(db_name)


@admin_required
def backup_restore(request):
    backup_path = _backup_dir()
    backup_files = sorted(backup_path.glob('*.sqlite3'), key=lambda p: p.stat().st_mtime, reverse=True)
    backups = [
        {
            'name': file.name,
            'size': file.stat().st_size,
            'modified': timezone.datetime.fromtimestamp(file.stat().st_mtime, tz=timezone.get_current_timezone()),
        }
        for file in backup_files
    ]
    current_db = _db_path()
    context = {
        'backups': backups,
        'current_db': current_db,
        'current_db_size': current_db.stat().st_size if current_db.exists() else 0,
    }
    return render(request, 'core/backup_restore.html', context)


@admin_required
def backup_download(request):
    current_db = _db_path()
    if not current_db.exists():
        raise Http404('Database file not found.')
    log_action(request.user, 'DOWNLOAD', DairyProfile.get_solo(), 'Database backup downloaded')
    filename = f'dairy_backup_{timezone.localtime().strftime("%Y%m%d_%H%M%S")}.sqlite3'
    return FileResponse(open(current_db, 'rb'), as_attachment=True, filename=filename)


@admin_required
@require_POST
def backup_create(request):
    current_db = _db_path()
    if not current_db.exists():
        messages.error(request, 'Database file not found.')
        return redirect('backup_restore')
    backup_path = _backup_dir() / f'dairy_backup_{timezone.localtime().strftime("%Y%m%d_%H%M%S")}.sqlite3'
    shutil.copy2(current_db, backup_path)
    log_action(request.user, 'CREATE', DairyProfile.get_solo(), f'Backup file created: {backup_path.name}')
    messages.success(request, f'Backup created: {backup_path.name}')
    return redirect('backup_restore')


@admin_required
@require_POST
def backup_upload(request):
    uploaded = request.FILES.get('backup_file')
    if not uploaded:
        messages.error(request, 'Please choose a backup file first.')
        return redirect('backup_restore')
    filename = uploaded.name.lower()
    if not (filename.endswith('.sqlite3') or filename.endswith('.db')):
        messages.error(request, 'Only .sqlite3 or .db backup files are allowed.')
        return redirect('backup_restore')

    current_db = _db_path()
    backup_path = _backup_dir()
    restore_copy = backup_path / f'uploaded_restore_{timezone.localtime().strftime("%Y%m%d_%H%M%S")}.sqlite3'
    with open(restore_copy, 'wb+') as destination:
        for chunk in uploaded.chunks():
            destination.write(chunk)

    safety_copy = backup_path / f'before_restore_{timezone.localtime().strftime("%Y%m%d_%H%M%S")}.sqlite3'
    if current_db.exists():
        shutil.copy2(current_db, safety_copy)
    log_action(request.user, 'UPLOAD', DairyProfile.get_solo(), f'Database restore requested from uploaded backup: {uploaded.name}. Safety copy: {safety_copy.name}')
    connection.close()
    shutil.copy2(restore_copy, current_db)
    messages.success(request, 'Backup uploaded and restored. Please restart the server once for best result.')
    return redirect('backup_restore')


@admin_required
def backup_file_download(request, filename):
    safe_name = os.path.basename(filename)
    path = _backup_dir() / safe_name
    if not path.exists() or path.suffix.lower() not in ['.sqlite3', '.db']:
        raise Http404('Backup file not found.')
    log_action(request.user, 'DOWNLOAD', DairyProfile.get_solo(), f'Saved backup downloaded: {safe_name}')
    return FileResponse(open(path, 'rb'), as_attachment=True, filename=safe_name)

# -----------------------------------------------------------------------------
# Remaining PDF requirement modules: batch management, bill template, settings,
# notification logs, complete MIS reports, customer portal, and mobile APIs.
# -----------------------------------------------------------------------------

@admin_required
def batch_update(request, pk):
    batch = get_object_or_404(ProductBatch, pk=pk)
    if request.method == 'POST':
        form = ProductBatchForm(request.POST, instance=batch)
        if form.is_valid():
            obj = form.save()
            log_action(request.user, 'UPDATE', obj, 'Product batch updated')
            messages.success(request, 'Batch updated successfully.')
            return redirect('receiving_list')
    else:
        form = ProductBatchForm(instance=batch)
    return render(request, 'core/form.html', {'form': form, 'title': f'Edit Batch {batch.batch_number}'})


@admin_required
@require_POST
def batch_delete(request, pk):
    batch = get_object_or_404(ProductBatch, pk=pk)
    try:
        log_action(request.user, 'DELETE', batch, 'Product batch deleted')
        batch.delete()
        messages.success(request, 'Batch deleted.')
    except Exception as exc:
        messages.error(request, f'Batch could not be deleted because it is already used in sales/stock records: {exc}')
    return redirect('receiving_list')


@admin_required
def bill_template_list(request):
    return render(request, 'core/simple_list.html', {
        'title': 'Bill Format / Invoice Templates',
        'items': BillTemplate.objects.all(),
        'columns': ['name', 'header_text', 'footer_text', 'show_pan', 'show_terms', 'active'],
        'add_url': 'bill_template_create',
        'edit_url': 'bill_template_update',
        'delete_url': 'bill_template_delete',
    })


@admin_required
def bill_template_create(request):
    return generic_list_create_update_delete(request, BillTemplate, BillTemplateForm, 'bill_template', 'Bill Template')


@admin_required
def bill_template_update(request, pk):
    return generic_list_create_update_delete(request, BillTemplate, BillTemplateForm, 'bill_template', 'Bill Template', pk=pk)


@admin_required
@require_POST
def bill_template_delete(request, pk):
    return generic_list_create_update_delete(request, BillTemplate, BillTemplateForm, 'bill_template', 'Bill Template', pk=pk, delete=True)


@admin_required
def fiscal_year_list(request):
    return render(request, 'core/simple_list.html', {
        'title': 'Fiscal Years / Nepali Invoice Numbering',
        'items': FiscalYear.objects.all(),
        'columns': ['name', 'start_date', 'end_date', 'invoice_prefix', 'active'],
        'add_url': 'fiscal_year_create',
        'edit_url': 'fiscal_year_update',
        'delete_url': 'fiscal_year_delete',
    })


@admin_required
def fiscal_year_create(request):
    return generic_list_create_update_delete(request, FiscalYear, FiscalYearForm, 'fiscal_year', 'Fiscal Year')


@admin_required
def fiscal_year_update(request, pk):
    return generic_list_create_update_delete(request, FiscalYear, FiscalYearForm, 'fiscal_year', 'Fiscal Year', pk=pk)


@admin_required
@require_POST
def fiscal_year_delete(request, pk):
    return generic_list_create_update_delete(request, FiscalYear, FiscalYearForm, 'fiscal_year', 'Fiscal Year', pk=pk, delete=True)


@role_required(Role.ADMIN, Role.SELLER)
def daily_customer_entries(request):
    query = request.GET.get('q', '').strip()
    entries = DailyCustomerProductEntry.objects.select_related('customer', 'product', 'batch', 'seller', 'shop', 'sale').order_by('-entry_date', '-created_at')
    if get_role(request.user) == Role.SELLER:
        entries = entries.filter(seller=request.user)
    if query:
        entries = entries.filter(Q(customer__name__icontains=query) | Q(customer__mobile_number__icontains=query) | Q(product__name__icontains=query) | Q(batch__batch_number__icontains=query))
    return render(request, 'core/daily_customer_entries.html', {'entries': entries[:500], 'query': query})


@role_required(Role.ADMIN, Role.SELLER)
@transaction.atomic
def daily_customer_entry_create(request):
    if request.method == 'POST':
        form = DailyCustomerProductEntryForm(request.POST, user=request.user)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.seller = request.user
            entry.product = entry.batch.product
            entry.rate = entry.product.selling_price
            batch = ProductBatch.objects.select_for_update().get(pk=entry.batch.pk)
            if batch.available_quantity < entry.quantity:
                messages.error(request, f'Not enough stock in batch {batch.batch_number}.')
            else:
                entry.batch = batch
                entry.save()
                batch.available_quantity -= entry.quantity
                batch.save()
                StockTransaction.objects.create(
                    transaction_type=StockTransaction.Type.OUT,
                    product=entry.product,
                    batch=batch,
                    quantity=entry.quantity,
                    reason=f'Daily customer entry for {entry.customer.name}',
                    created_by=request.user,
                )
                log_action(request.user, 'CREATE', entry, 'Daily product added to monthly customer account')
                messages.success(request, 'Daily product added to customer account. It can be billed monthly.')
                return redirect('daily_customer_entries')
    else:
        form = DailyCustomerProductEntryForm(user=request.user)
    return render(request, 'core/form.html', {'form': form, 'title': 'Add Daily Product to Customer'})


@role_required(Role.ADMIN, Role.SELLER)
def monthly_customer_search(request):
    query = request.GET.get('q', '').strip()
    customers = Customer.objects.filter(status=Customer.Status.ACTIVE, customer_type=Customer.Type.REGULAR)
    if query:
        customers = customers.filter(Q(name__icontains=query) | Q(mobile_number__icontains=query) | Q(address__icontains=query))
    rows = []
    for customer in customers[:200]:
        qs = DailyCustomerProductEntry.objects.filter(customer=customer, billed=False)
        if get_role(request.user) == Role.SELLER:
            qs = qs.filter(seller=request.user)
        total = qs.aggregate(total=Sum('amount'), count=Count('id'))
        rows.append({'customer': customer, 'unbilled_total': total['total'] or Decimal('0.00'), 'unbilled_count': total['count'] or 0})
    return render(request, 'core/monthly_customer_search.html', {'rows': rows, 'query': query})


@role_required(Role.ADMIN, Role.SELLER)
def monthly_bill_create(request):
    initial = {}
    customer_id = request.GET.get('customer')
    if customer_id:
        initial['customer'] = customer_id
    today = timezone.localdate()
    initial.setdefault('period_start', today.replace(day=1))
    initial.setdefault('period_end', today)
    if request.method == 'POST':
        form = MonthlyBillForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                sale = _create_monthly_sale(request, form.cleaned_data)
                messages.success(request, f'Monthly bill generated: {sale.bill_number}')
                return redirect('sale_detail', pk=sale.pk)
            except ValueError as exc:
                messages.error(request, str(exc))
    else:
        form = MonthlyBillForm(initial=initial, user=request.user)
    return render(request, 'core/monthly_bill_form.html', {'form': form, 'title': 'Generate Monthly Bill'})


@transaction.atomic
def _create_monthly_sale(request, data):
    entries = DailyCustomerProductEntry.objects.select_related('product', 'batch').filter(
        customer=data['customer'],
        entry_date__gte=data['period_start'],
        entry_date__lte=data['period_end'],
        billed=False,
    )
    if get_role(request.user) == Role.SELLER:
        entries = entries.filter(seller=request.user)
    entries = list(entries)
    if not entries:
        raise ValueError('No unbilled daily product entries found for this customer and period.')
    subtotal = sum((e.amount for e in entries), Decimal('0.00'))
    discount = data.get('discount') or Decimal('0.00')
    paid = data.get('paid_amount') or Decimal('0.00')
    if discount > subtotal:
        raise ValueError('Discount cannot exceed subtotal.')
    sale = Sale.objects.create(
        seller=request.user,
        customer=data['customer'],
        shop=data.get('shop'),
        payment_method=data['payment_method'],
        discount=discount,
        total_amount=subtotal - discount,
        paid_amount=paid,
        due_amount=max(subtotal - discount - paid, Decimal('0.00')),
        status=Sale.Status.DUE if max(subtotal - discount - paid, Decimal('0.00')) > 0 else Sale.Status.PAID,
        is_monthly_bill=True,
        billing_period_start=data['period_start'],
        billing_period_end=data['period_end'],
    )
    grouped = {}
    for e in entries:
        key = (e.product_id, e.batch_id, e.rate)
        grouped.setdefault(key, {'product': e.product, 'batch': e.batch, 'quantity': Decimal('0.00'), 'amount': Decimal('0.00'), 'rate': e.rate})
        grouped[key]['quantity'] += e.quantity
        grouped[key]['amount'] += e.amount
    for row in grouped.values():
        SaleItem.objects.create(
            sale=sale,
            product=row['product'],
            batch=row['batch'],
            quantity=row['quantity'],
            rate=row['rate'],
            item_discount=Decimal('0.00'),
            amount=row['amount'],
        )
    DailyCustomerProductEntry.objects.filter(pk__in=[e.pk for e in entries]).update(billed=True, sale=sale)
    log_action(request.user, 'CREATE', sale, f'Monthly bill generated for {len(entries)} daily entries from {data["period_start"]} to {data["period_end"]}')
    return sale


@admin_required
def system_settings(request):
    settings_qs = SystemSetting.objects.all()
    return render(request, 'core/simple_list.html', {
        'title': 'Website / Mobile System Settings',
        'items': settings_qs,
        'columns': ['key', 'value', 'description', 'updated_at'],
        'add_url': 'system_setting_create',
        'edit_url': 'system_setting_update',
        'delete_url': 'system_setting_delete',
    })


@admin_required
def system_setting_create(request):
    return generic_list_create_update_delete(request, SystemSetting, SystemSettingForm, 'system_setting', 'System Setting')


@admin_required
def system_setting_update(request, pk):
    return generic_list_create_update_delete(request, SystemSetting, SystemSettingForm, 'system_setting', 'System Setting', pk=pk)


@admin_required
@require_POST
def system_setting_delete(request, pk):
    return generic_list_create_update_delete(request, SystemSetting, SystemSettingForm, 'system_setting', 'System Setting', pk=pk, delete=True)


@login_required
def notifications(request):
    role = get_role(request.user)
    if role == Role.ADMIN:
        logs = NotificationLog.objects.select_related('recipient', 'created_by').all()
    else:
        logs = NotificationLog.objects.select_related('recipient', 'created_by').filter(Q(recipient=request.user) | Q(target_role=role))
    return render(request, 'core/notifications.html', {'notifications': logs[:300], 'title': 'Notifications'})


@admin_required
def notification_create(request):
    if request.method == 'POST':
        form = NotificationForm(request.POST)
        if form.is_valid():
            note = form.save(commit=False)
            note.created_by = request.user
            note.save()
            log_action(request.user, 'CREATE', note, 'Notification created')
            messages.success(request, 'Notification saved/sent successfully.')
            return redirect('notifications')
    else:
        form = NotificationForm(initial={'channel': NotificationLog.Channel.WEB, 'status': NotificationLog.Status.SENT})
    return render(request, 'core/form.html', {'form': form, 'title': 'Create Notification'})


@login_required
def notification_mark_read(request, pk):
    note = get_object_or_404(NotificationLog, pk=pk)
    role = get_role(request.user)
    if role != Role.ADMIN and note.recipient != request.user and note.target_role != role:
        messages.error(request, 'You cannot update this notification.')
        return redirect('notifications')
    note.mark_read()
    messages.success(request, 'Notification marked as read.')
    return redirect('notifications')


@login_required
def product_catalog(request):
    query = request.GET.get('q', '').strip()
    products = Product.objects.filter(active=True).select_related('unit')
    if query:
        products = products.filter(Q(name__icontains=query) | Q(code__icontains=query) | Q(category__icontains=query))
    rows = []
    for product in products:
        batches = product.batches.filter(status=ProductBatch.Status.AVAILABLE, available_quantity__gt=0).order_by('expiry_date', 'received_date')[:5]
        rows.append({'product': product, 'stock': product.current_stock, 'batches': batches})
    return render(request, 'core/product_catalog.html', {'rows': rows, 'query': query})


@customer_required
def customer_profile(request):
    customer = _customer_for_user(request.user)
    if not customer:
        messages.error(request, 'No customer profile is linked with your account. Please contact admin.')
        return redirect('customer_dashboard')
    if request.method == 'POST':
        form = CustomerProfileForm(request.POST, instance=customer)
        if form.is_valid():
            obj = form.save()
            request.user.email = obj.email
            request.user.profile.phone = obj.mobile_number
            request.user.profile.address = obj.address
            request.user.profile.save()
            request.user.save(update_fields=['email'])
            log_action(request.user, 'UPDATE', obj, 'Customer updated own profile')
            messages.success(request, 'Profile updated successfully.')
            return redirect('customer_profile')
    else:
        form = CustomerProfileForm(instance=customer)
    return render(request, 'core/form.html', {'form': form, 'title': 'My Profile'})


@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            log_action(request.user, 'UPDATE', request.user, 'Password changed')
            messages.success(request, 'Password changed successfully.')
            return redirect('dashboard')
    else:
        form = PasswordChangeForm(request.user)
        for field in form.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')
    return render(request, 'core/form.html', {'form': form, 'title': 'Change Password'})


@login_required
def set_language(request, code):
    if code not in ['en', 'ne']:
        code = 'en'
    request.session['site_language'] = code
    response = redirect(request.META.get('HTTP_REFERER') or 'dashboard')
    response.set_cookie('django_language', code)
    return response


def _apply_sale_filters(sales, request):
    if get_role(request.user) == Role.SELLER:
        sales = sales.filter(seller=request.user)
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    product = request.GET.get('product')
    shop = request.GET.get('shop')
    payment = request.GET.get('payment')
    customer = request.GET.get('customer')
    seller = request.GET.get('seller')
    if date_from:
        sales = sales.filter(created_at__date__gte=date_from)
    if date_to:
        sales = sales.filter(created_at__date__lte=date_to)
    if shop:
        sales = sales.filter(shop_id=shop)
    if payment:
        sales = sales.filter(payment_method_id=payment)
    if customer:
        sales = sales.filter(customer_id=customer)
    if seller:
        sales = sales.filter(seller_id=seller)
    if product:
        sales = sales.filter(items__product_id=product).distinct()
    return sales


def _mis_rows(request, report_type):
    sales = _apply_sale_filters(Sale.objects.select_related('customer', 'seller', 'shop', 'payment_method'), request)
    product_filter = request.GET.get('product')
    items = SaleItem.objects.select_related('sale', 'product', 'batch').filter(sale__in=sales)
    if product_filter:
        items = items.filter(product_id=product_filter)

    def money(value):
        return value or Decimal('0.00')

    if report_type == 'daily_sales':
        qs = sales.annotate(period=TruncDate('created_at')).values('period').annotate(bills=Count('id'), total=Sum('total_amount'), paid=Sum('paid_amount'), due=Sum('due_amount')).order_by('-period')
        return [('period', 'Date'), ('bills', 'Bills'), ('total', 'Total Sales'), ('paid', 'Paid'), ('due', 'Due')], list(qs)

    if report_type == 'product_wise':
        qs = items.values('product__name', 'product__code').annotate(quantity=Sum('quantity'), total=Sum('amount')).order_by('product__name')
        return [('product__name', 'Product'), ('product__code', 'Code'), ('quantity', 'Qty Sold'), ('total', 'Sales Amount')], list(qs)

    if report_type == 'batch_wise':
        qs = items.values('batch__batch_number', 'product__name').annotate(quantity=Sum('quantity'), total=Sum('amount')).order_by('batch__batch_number')
        return [('batch__batch_number', 'Batch Number'), ('product__name', 'Product'), ('quantity', 'Qty Sold'), ('total', 'Sales Amount')], list(qs)

    if report_type == 'customer_wise':
        qs = sales.values('customer__name', 'customer__mobile_number').annotate(bills=Count('id'), total=Sum('total_amount'), paid=Sum('paid_amount'), due=Sum('due_amount')).order_by('customer__name')
        return [('customer__name', 'Customer'), ('customer__mobile_number', 'Mobile'), ('bills', 'Bills'), ('total', 'Total'), ('paid', 'Paid'), ('due', 'Due')], list(qs)

    if report_type == 'seller_wise':
        qs = sales.values('seller__username', 'seller__first_name', 'seller__last_name').annotate(bills=Count('id'), total=Sum('total_amount'), due=Sum('due_amount')).order_by('seller__username')
        return [('seller__username', 'Seller'), ('bills', 'Bills'), ('total', 'Total'), ('due', 'Due')], list(qs)

    if report_type == 'shop_wise':
        qs = sales.values('shop__name').annotate(bills=Count('id'), total=Sum('total_amount'), due=Sum('due_amount')).order_by('shop__name')
        return [('shop__name', 'Shop / Branch'), ('bills', 'Bills'), ('total', 'Total'), ('due', 'Due')], list(qs)

    if report_type == 'payment_method':
        qs = sales.values('payment_method__name').annotate(bills=Count('id'), total=Sum('total_amount'), due=Sum('due_amount')).order_by('payment_method__name')
        return [('payment_method__name', 'Payment Method'), ('bills', 'Bills'), ('total', 'Total'), ('due', 'Due')], list(qs)

    if report_type == 'stock':
        rows = []
        for p in Product.objects.filter(active=True).select_related('unit'):
            rows.append({'product': p.name, 'code': p.code, 'stock': p.current_stock, 'unit': p.unit.short_form, 'threshold': p.low_stock_threshold, 'status': 'Low Stock' if p.current_stock <= p.low_stock_threshold else 'Available'})
        return [('product', 'Product'), ('code', 'Code'), ('stock', 'Available Stock'), ('unit', 'Unit'), ('threshold', 'Low Stock Threshold'), ('status', 'Status')], rows

    if report_type == 'low_stock':
        rows = []
        for p in Product.objects.filter(active=True).select_related('unit'):
            if p.current_stock <= p.low_stock_threshold:
                rows.append({'product': p.name, 'code': p.code, 'stock': p.current_stock, 'unit': p.unit.short_form, 'threshold': p.low_stock_threshold})
        return [('product', 'Product'), ('code', 'Code'), ('stock', 'Available Stock'), ('unit', 'Unit'), ('threshold', 'Threshold')], rows

    if report_type == 'expired_product':
        qs = ProductBatch.objects.filter(Q(status=ProductBatch.Status.EXPIRED) | Q(expiry_date__lt=timezone.localdate())).select_related('product', 'product__unit').order_by('expiry_date')
        rows = [{'batch': b.batch_number, 'product': b.product.name, 'received': b.received_date, 'expiry': b.expiry_date, 'available': b.available_quantity, 'unit': b.product.unit.short_form} for b in qs]
        return [('batch', 'Batch'), ('product', 'Product'), ('received', 'Received Date'), ('expiry', 'Expiry Date'), ('available', 'Available'), ('unit', 'Unit')], rows

    if report_type == 'monthly_sales':
        qs = sales.annotate(period=TruncMonth('created_at')).values('period').annotate(bills=Count('id'), total=Sum('total_amount'), paid=Sum('paid_amount'), due=Sum('due_amount')).order_by('-period')
        return [('period', 'Month'), ('bills', 'Bills'), ('total', 'Total'), ('paid', 'Paid'), ('due', 'Due')], list(qs)

    if report_type == 'profit_loss':
        profit_expr = ExpressionWrapper((F('rate') - F('product__cost_price')) * F('quantity') - F('item_discount'), output_field=DecimalField(max_digits=12, decimal_places=2))
        cost_expr = ExpressionWrapper(F('product__cost_price') * F('quantity'), output_field=DecimalField(max_digits=12, decimal_places=2))
        qs = items.annotate(cost_line=cost_expr, profit_line=profit_expr).values('product__name').annotate(quantity=Sum('quantity'), revenue=Sum('amount'), cost=Sum('cost_line'), profit=Sum('profit_line')).order_by('product__name')
        return [('product__name', 'Product'), ('quantity', 'Qty Sold'), ('revenue', 'Revenue'), ('cost', 'Cost'), ('profit', 'Profit / Loss')], list(qs)

    if report_type == 'due_payment':
        qs = sales.filter(due_amount__gt=0).values('customer__name', 'customer__mobile_number').annotate(bills=Count('id'), due=Sum('due_amount'), total=Sum('total_amount')).order_by('-due')
        return [('customer__name', 'Customer'), ('customer__mobile_number', 'Mobile'), ('bills', 'Due Bills'), ('total', 'Total Sale'), ('due', 'Due Amount')], list(qs)

    return _mis_rows(request, 'daily_sales')


REPORT_TYPES = [
    ('daily_sales', 'Daily Sales Report'),
    ('product_wise', 'Product-wise Sales Report'),
    ('batch_wise', 'Batch-wise Report'),
    ('customer_wise', 'Customer-wise Report'),
    ('seller_wise', 'Seller-wise Report'),
    ('shop_wise', 'Shop-wise Report'),
    ('payment_method', 'Payment Method Report'),
    ('stock', 'Stock Report'),
    ('low_stock', 'Low Stock Report'),
    ('expired_product', 'Expired Product Report'),
    ('monthly_sales', 'Monthly Sales Report'),
    ('profit_loss', 'Profit/Loss Report'),
    ('due_payment', 'Due Payment Report'),
]


@role_required(Role.ADMIN, Role.SELLER)
def mis_reports(request):
    report_type = request.GET.get('type') or 'daily_sales'
    valid_types = dict(REPORT_TYPES)
    if report_type not in valid_types:
        report_type = 'daily_sales'
    columns, rows = _mis_rows(request, report_type)

    if request.method == 'POST':
        name = request.POST.get('name') or valid_types[report_type]
        SavedReportConfig.objects.create(name=name, report_type=report_type, filters=dict(request.GET), created_by=request.user)
        log_action(request.user, 'CREATE', DairyProfile.get_solo(), f'Saved report configuration: {name}')
        messages.success(request, 'Report configuration saved.')
        return redirect(f'{request.path}?{request.GET.urlencode()}')

    export = request.GET.get('export')
    if export == 'excel':
        return export_generic_excel(valid_types[report_type], columns, rows)
    if export == 'pdf':
        return export_generic_pdf(valid_types[report_type], columns, rows)

    context = {
        'report_types': REPORT_TYPES,
        'report_type': report_type,
        'report_title': valid_types[report_type],
        'columns': columns,
        'rows': rows,
        'filters': request.GET,
        'products': Product.objects.filter(active=True),
        'shops': Shop.objects.filter(active=True),
        'payments': PaymentMethod.objects.filter(active=True),
        'customers': Customer.objects.all(),
        'sellers': User.objects.filter(pk=request.user.pk) if get_role(request.user) == Role.SELLER else User.objects.filter(profile__role=Role.SELLER),
        'saved_reports': SavedReportConfig.objects.filter(created_by=request.user)[:8],
    }
    return render(request, 'core/mis_reports.html', context)


def export_generic_excel(title, columns, rows):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = title[:31]
    ws.append([label for _, label in columns])
    for row in rows:
        ws.append([row.get(key, '') for key, _ in columns])
    buffer = BytesIO()
    wb.save(buffer)
    response = HttpResponse(buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{title.lower().replace(" ", "_").replace("/", "_")}.xlsx"'
    return response


def export_generic_pdf(title, columns, rows):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen import canvas
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)
    y = height - 42
    p.setFont('Helvetica-Bold', 15)
    p.drawString(40, y, title)
    y -= 20
    p.setFont('Helvetica', 8)
    p.drawString(40, y, f'Generated: {timezone.localtime():%Y-%m-%d %H:%M}')
    y -= 25
    x_positions = [40 + i * max(90, int((width - 80) / max(len(columns), 1))) for i in range(len(columns))]
    p.setFont('Helvetica-Bold', 8)
    for (key, label), x in zip(columns, x_positions):
        p.drawString(x, y, label[:18])
    y -= 14
    p.setFont('Helvetica', 7)
    for row in rows:
        for (key, _), x in zip(columns, x_positions):
            p.drawString(x, y, str(row.get(key, ''))[:20])
        y -= 12
        if y < 35:
            p.showPage()
            y = height - 42
    p.showPage()
    p.save()
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{title.lower().replace(" ", "_").replace("/", "_")}.pdf"'
    return response


def _customer_for_user(user):
    customer = Customer.objects.filter(user=user).first()
    if not customer and getattr(user, 'profile', None):
        customer = Customer.objects.filter(mobile_number=user.profile.phone).first()
    return customer


def _api_error(message, status=400):
    return JsonResponse({'ok': False, 'error': message}, status=status)


def _api_user(request):
    header = request.headers.get('Authorization', '')
    token = ''
    if header.lower().startswith('token '):
        token = header.split(' ', 1)[1].strip()
    elif request.GET.get('token'):
        token = request.GET.get('token')
    if not token:
        return None
    auth = MobileAuthToken.objects.select_related('user', 'user__profile').filter(key=token, user__is_active=True).first()
    return auth.user if auth else None


def api_auth_required(view_func):
    def wrapper(request, *args, **kwargs):
        user = _api_user(request)
        if not user:
            return _api_error('Invalid or missing API token.', 401)
        request.api_user = user
        return view_func(request, *args, **kwargs)
    return wrapper


def _product_to_dict(product):
    return {
        'id': product.id,
        'name': product.name,
        'code': product.code,
        'category': product.category,
        'unit': product.unit.short_form,
        'selling_price': float(product.selling_price),
        'available_stock': float(product.current_stock),
        'low_stock_threshold': float(product.low_stock_threshold),
    }


def _sale_to_dict(sale, include_items=False):
    data = {
        'id': sale.id,
        'bill_number': sale.bill_number,
        'date': timezone.localtime(sale.created_at).strftime('%Y-%m-%d %H:%M'),
        'customer': sale.customer.name,
        'seller': sale.seller.get_full_name() or sale.seller.username,
        'shop': sale.shop.name if sale.shop else '',
        'payment_method': sale.payment_method.name,
        'total_amount': float(sale.total_amount),
        'paid_amount': float(sale.paid_amount),
        'return_amount': float(sale.return_amount),
        'due_amount': float(sale.due_amount),
        'status': sale.status,
    }
    if include_items:
        data['items'] = [
            {
                'product': item.product.name,
                'batch_number': item.batch.batch_number,
                'quantity': float(item.quantity),
                'rate': float(item.rate),
                'discount': float(item.item_discount),
                'amount': float(item.amount),
            }
            for item in sale.items.select_related('product', 'batch').all()
        ]
    return data


@csrf_exempt
@require_POST
def api_login(request):
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload = request.POST
    login_id = (payload.get('username') or payload.get('mobile') or '').strip()
    password = payload.get('password') or ''
    username = login_id
    if login_id and not User.objects.filter(username=login_id).exists():
        customer = Customer.objects.filter(mobile_number=login_id, user__isnull=False).select_related('user').first()
        if customer:
            username = customer.user.username
        else:
            matched_user = User.objects.filter(profile__phone=login_id).first()
            if matched_user:
                username = matched_user.username
    user = authenticate(username=username, password=password)
    if not user:
        return _api_error('Invalid login details.', 401)
    token, _ = MobileAuthToken.objects.get_or_create(user=user)
    return JsonResponse({'ok': True, 'token': token.key, 'user': {'id': user.id, 'username': user.username, 'name': user.get_full_name(), 'role': get_role(user)}})


@require_GET
@api_auth_required
def api_customer_profile(request):
    user = request.api_user
    customer = _customer_for_user(user)
    return JsonResponse({'ok': True, 'profile': {
        'username': user.username,
        'name': customer.name if customer else user.get_full_name(),
        'mobile_number': customer.mobile_number if customer else getattr(user.profile, 'phone', ''),
        'address': customer.address if customer else getattr(user.profile, 'address', ''),
        'email': customer.email if customer else user.email,
        'role': get_role(user),
    }})


@require_GET
@api_auth_required
def api_products(request):
    products = Product.objects.filter(active=True).select_related('unit')
    return JsonResponse({'ok': True, 'products': [_product_to_dict(p) for p in products]})


@require_GET
@api_auth_required
def api_customer_purchases(request):
    customer = _customer_for_user(request.api_user)
    if not customer:
        return JsonResponse({'ok': True, 'purchases': []})
    items = SaleItem.objects.filter(sale__customer=customer).select_related('sale', 'product', 'batch').order_by('-sale__created_at')
    purchases = [{
        'date': timezone.localtime(item.sale.created_at).strftime('%Y-%m-%d %H:%M'),
        'bill_number': item.sale.bill_number,
        'product': item.product.name,
        'batch_number': item.batch.batch_number,
        'quantity': float(item.quantity),
        'rate': float(item.rate),
        'amount': float(item.amount),
        'payment_method': item.sale.payment_method.name,
        'status': item.sale.status,
    } for item in items]
    return JsonResponse({'ok': True, 'purchases': purchases})


@require_GET
@api_auth_required
def api_bills(request):
    user = request.api_user
    role = get_role(user)
    sales = Sale.objects.select_related('customer', 'seller', 'shop', 'payment_method').all()
    if role == Role.CUSTOMER:
        customer = _customer_for_user(user)
        sales = sales.filter(customer=customer) if customer else Sale.objects.none()
    elif role == Role.SELLER:
        sales = sales.filter(seller=user)
    return JsonResponse({'ok': True, 'bills': [_sale_to_dict(sale) for sale in sales.order_by('-created_at')[:200]]})


@require_GET
@api_auth_required
def api_bill_detail(request, pk):
    user = request.api_user
    role = get_role(user)
    sale = get_object_or_404(Sale.objects.select_related('customer', 'seller', 'shop', 'payment_method').prefetch_related('items__product', 'items__batch'), pk=pk)
    if role == Role.CUSTOMER:
        customer = _customer_for_user(user)
        if not customer or sale.customer_id != customer.id:
            return _api_error('You cannot view this bill.', 403)
    if role == Role.SELLER and sale.seller_id != user.id:
        return _api_error('You cannot view this bill.', 403)
    return JsonResponse({'ok': True, 'bill': _sale_to_dict(sale, include_items=True)})


@require_GET
@api_auth_required
def api_notifications(request):
    user = request.api_user
    role = get_role(user)
    notifications = NotificationLog.objects.filter(Q(recipient=user) | Q(target_role=role)).order_by('-created_at')[:100]
    data = [{
        'id': n.id,
        'title': n.title,
        'message': n.message,
        'channel': n.channel,
        'status': n.status,
        'created_at': timezone.localtime(n.created_at).strftime('%Y-%m-%d %H:%M'),
    } for n in notifications]
    return JsonResponse({'ok': True, 'notifications': data})
