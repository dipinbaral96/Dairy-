from django.contrib import admin
from .models import (
    AuditLog, BillTemplate, Customer, DairyProfile, PaymentMethod, Product,
    ProductBatch, Sale, SaleItem, Seller, Shop, StockTransaction, Unit, UserProfile,
    MobileAuthToken, NotificationLog, SavedReportConfig, SystemSetting, FiscalYear, DailyCustomerProductEntry
)


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('bill_number', 'customer', 'seller', 'total_amount', 'paid_amount', 'due_amount', 'status', 'created_at')
    list_filter = ('status', 'payment_method', 'shop')
    search_fields = ('bill_number', 'customer__name', 'customer__mobile_number')
    inlines = [SaleItemInline]


admin.site.register(UserProfile)
admin.site.register(DairyProfile)
admin.site.register(Shop)
admin.site.register(Unit)
admin.site.register(Product)
admin.site.register(ProductBatch)
admin.site.register(StockTransaction)
admin.site.register(Customer)
admin.site.register(Seller)
admin.site.register(PaymentMethod)
admin.site.register(BillTemplate)
admin.site.register(AuditLog)
admin.site.register(MobileAuthToken)
admin.site.register(NotificationLog)
admin.site.register(SavedReportConfig)
admin.site.register(SystemSetting)

admin.site.register(FiscalYear)
admin.site.register(DailyCustomerProductEntry)
