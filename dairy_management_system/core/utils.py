from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from .models import AuditLog, ProductBatch, SaleItem, StockTransaction


def log_action(user, action, instance, notes=''):
    AuditLog.objects.create(
        user=user if user.is_authenticated else None,
        action=action,
        model_name=instance.__class__.__name__,
        object_repr=str(instance),
        notes=notes,
    )


@transaction.atomic
def create_sale_with_items(user, sale, item_forms):
    valid_lines = []
    subtotal = Decimal('0.00')

    for form in item_forms:
        if not form.cleaned_data or form.cleaned_data.get('DELETE'):
            continue
        batch = form.cleaned_data['batch']
        quantity = form.cleaned_data['quantity']
        item_discount = form.cleaned_data.get('item_discount') or Decimal('0.00')
        batch = ProductBatch.objects.select_for_update().get(pk=batch.pk)
        if batch.available_quantity < quantity:
            raise ValueError(f'Not enough stock in batch {batch.batch_number}. Available: {batch.available_quantity}')
        rate = batch.product.selling_price
        amount = (quantity * rate) - item_discount
        if amount < 0:
            raise ValueError(f'Item discount cannot exceed amount for {batch.batch_number}.')
        valid_lines.append((batch, quantity, rate, item_discount, amount))
        subtotal += amount

    if not valid_lines:
        raise ValueError('Add at least one product line before generating bill.')

    if sale.discount > subtotal:
        raise ValueError('Overall discount cannot exceed subtotal.')

    sale.total_amount = subtotal - sale.discount
    sale.due_amount = max(sale.total_amount - sale.paid_amount, Decimal('0.00'))
    sale.status = sale.Status.DUE if sale.due_amount > 0 else sale.Status.PAID
    sale.seller = user
    sale.save()

    for batch, quantity, rate, item_discount, amount in valid_lines:
        SaleItem.objects.create(
            sale=sale,
            product=batch.product,
            batch=batch,
            quantity=quantity,
            rate=rate,
            item_discount=item_discount,
            amount=amount,
        )
        batch.available_quantity -= quantity
        batch.save()
        StockTransaction.objects.create(
            transaction_type=StockTransaction.Type.OUT,
            product=batch.product,
            batch=batch,
            quantity=quantity,
            reason=f'Sale {sale.bill_number}',
            created_by=user,
        )

    log_action(user, 'CREATE', sale, f'Sale generated with {len(valid_lines)} item(s).')
    return sale
