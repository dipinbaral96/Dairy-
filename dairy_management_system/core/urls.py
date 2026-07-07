from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.DairyLoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),

    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('seller-dashboard/', views.seller_dashboard, name='seller_dashboard'),
    path('customer-dashboard/', views.customer_dashboard, name='customer_dashboard'),

    path('dairy-profile/', views.dairy_profile, name='dairy_profile'),

    path('users/', views.user_list, name='user_list'),
    path('users/add/', views.user_create, name='user_create'),
    path('users/<int:pk>/edit/', views.user_update, name='user_update'),
    path('users/<int:pk>/delete/', views.user_delete, name='user_delete'),

    path('shops/', views.shop_list, name='shop_list'),
    path('shops/add/', views.shop_create, name='shop_create'),
    path('shops/<int:pk>/edit/', views.shop_update, name='shop_update'),
    path('shops/<int:pk>/delete/', views.shop_delete, name='shop_delete'),

    path('units/', views.unit_list, name='unit_list'),
    path('units/add/', views.unit_create, name='unit_create'),
    path('units/<int:pk>/edit/', views.unit_update, name='unit_update'),
    path('units/<int:pk>/delete/', views.unit_delete, name='unit_delete'),

    path('products/', views.product_list, name='product_list'),
    path('products/add/', views.product_create, name='product_create'),
    path('products/<int:pk>/edit/', views.product_update, name='product_update'),
    path('products/<int:pk>/delete/', views.product_delete, name='product_delete'),

    path('customers/', views.customer_list, name='customer_list'),
    path('customers/add/', views.customer_create, name='customer_create'),
    path('customers/<int:pk>/edit/', views.customer_update, name='customer_update'),
    path('customers/<int:pk>/delete/', views.customer_delete, name='customer_delete'),

    path('payments/', views.payment_list, name='payment_list'),
    path('payments/add/', views.payment_create, name='payment_create'),
    path('payments/<int:pk>/edit/', views.payment_update, name='payment_update'),
    path('payments/<int:pk>/delete/', views.payment_delete, name='payment_delete'),

    path('fiscal-years/', views.fiscal_year_list, name='fiscal_year_list'),
    path('fiscal-years/add/', views.fiscal_year_create, name='fiscal_year_create'),
    path('fiscal-years/<int:pk>/edit/', views.fiscal_year_update, name='fiscal_year_update'),
    path('fiscal-years/<int:pk>/delete/', views.fiscal_year_delete, name='fiscal_year_delete'),

    path('daily-customer-entries/', views.daily_customer_entries, name='daily_customer_entries'),
    path('daily-customer-entries/add/', views.daily_customer_entry_create, name='daily_customer_entry_create'),
    path('monthly-customers/', views.monthly_customer_search, name='monthly_customer_search'),
    path('monthly-bills/generate/', views.monthly_bill_create, name='monthly_bill_create'),

    path('receiving/', views.receiving_list, name='receiving_list'),
    path('receiving/add/', views.receiving_create, name='receiving_create'),

    path('batch-search/', views.batch_search, name='batch_search'),
    path('sales/', views.sale_list, name='sale_list'),
    path('sales/add/', views.sale_create, name='sale_create'),
    path('sales/<int:pk>/', views.sale_detail, name='sale_detail'),
    path('sales/<int:pk>/pdf/', views.sale_pdf, name='sale_pdf'),

    path('reports/sales/', views.sales_report, name='sales_report'),
    path('reports/stock/', views.stock_report, name='stock_report'),
    path('activity-logs/', views.audit_logs, name='audit_logs'),
    path('backup/', views.backup_restore, name='backup_restore'),
    path('backup/download/', views.backup_download, name='backup_download'),
    path('backup/create/', views.backup_create, name='backup_create'),
    path('backup/upload/', views.backup_upload, name='backup_upload'),
    path('backup/file/<str:filename>/', views.backup_file_download, name='backup_file_download'),

    path('language/<str:code>/', views.set_language, name='set_language'),
    path('change-password/', views.change_password, name='change_password'),
    path('product-catalog/', views.product_catalog, name='product_catalog'),
    path('customer-profile/', views.customer_profile, name='customer_profile'),

    path('receiving/<int:pk>/edit/', views.batch_update, name='batch_update'),
    path('receiving/<int:pk>/delete/', views.batch_delete, name='batch_delete'),

    path('bill-templates/', views.bill_template_list, name='bill_template_list'),
    path('bill-templates/add/', views.bill_template_create, name='bill_template_create'),
    path('bill-templates/<int:pk>/edit/', views.bill_template_update, name='bill_template_update'),
    path('bill-templates/<int:pk>/delete/', views.bill_template_delete, name='bill_template_delete'),

    path('system-settings/', views.system_settings, name='system_settings'),
    path('system-settings/add/', views.system_setting_create, name='system_setting_create'),
    path('system-settings/<int:pk>/edit/', views.system_setting_update, name='system_setting_update'),
    path('system-settings/<int:pk>/delete/', views.system_setting_delete, name='system_setting_delete'),

    path('notifications/', views.notifications, name='notifications'),
    path('notifications/add/', views.notification_create, name='notification_create'),
    path('notifications/<int:pk>/read/', views.notification_mark_read, name='notification_mark_read'),

    path('reports/mis/', views.mis_reports, name='mis_reports'),

    path('api/login/', views.api_login, name='api_login'),
    path('api/customer/profile/', views.api_customer_profile, name='api_customer_profile'),
    path('api/products/', views.api_products, name='api_products'),
    path('api/customer/purchases/', views.api_customer_purchases, name='api_customer_purchases'),
    path('api/bills/', views.api_bills, name='api_bills'),
    path('api/bill/<int:pk>/', views.api_bill_detail, name='api_bill_detail'),
    path('api/notifications/', views.api_notifications, name='api_notifications'),
]
