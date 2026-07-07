from django.templatetags.static import static
from .decorators import get_role
from .models import DairyProfile, NotificationLog, Role
from django.db.models import Q


NAV_LABELS = {
    'en': {
        'dashboard': 'Dashboard', 'administration': 'Administration', 'dairy_profile': 'Dairy Profile',
        'users': 'Users', 'shops': 'Shops / Branches', 'units': 'Units', 'products': 'Products',
        'daily_receiving': 'Daily Receiving', 'customers': 'Customers', 'payments': 'Payment Methods',
        'bill_format': 'Bill Format', 'system_settings': 'System Settings', 'sales_reports': 'Sales & Reports',
        'bills_sales': 'Bills / Sales', 'mis_reports': 'MIS Reports', 'sales_report': 'Sales Report',
        'stock_report': 'Stock Report', 'activity_logs': 'Activity Logs', 'backup_restore': 'Backup / Restore',
        'notifications': 'Notifications', 'seller_tools': 'Seller Tools', 'product_search': 'Product / Batch Search',
        'generate_bill': 'Generate Bill', 'my_bills': 'My Bills', 'customer': 'Customer', 'my_profile_bills': 'My Profile & Bills',
        'product_catalog': 'Product Catalog', 'change_password': 'Change Password', 'logout': 'Logout'
    },
    'ne': {
        'dashboard': 'ड्यासबोर्ड', 'administration': 'प्रशासन', 'dairy_profile': 'डेरी प्रोफाइल',
        'users': 'प्रयोगकर्ता', 'shops': 'शाखा / पसल', 'units': 'इकाइहरू', 'products': 'उत्पादनहरू',
        'daily_receiving': 'दैनिक प्राप्ति', 'customers': 'ग्राहकहरू', 'payments': 'भुक्तानी विधि',
        'bill_format': 'बिल ढाँचा', 'system_settings': 'सिस्टम सेटिङ', 'sales_reports': 'बिक्री र रिपोर्ट',
        'bills_sales': 'बिल / बिक्री', 'mis_reports': 'MIS रिपोर्ट', 'sales_report': 'बिक्री रिपोर्ट',
        'stock_report': 'स्टक रिपोर्ट', 'activity_logs': 'गतिविधि लग', 'backup_restore': 'ब्याकअप / रिस्टोर',
        'notifications': 'सूचनाहरू', 'seller_tools': 'बिक्रेता उपकरण', 'product_search': 'उत्पादन / ब्याच खोज',
        'generate_bill': 'बिल बनाउनुहोस्', 'my_bills': 'मेरो बिलहरू', 'customer': 'ग्राहक', 'my_profile_bills': 'मेरो प्रोफाइल र बिल',
        'product_catalog': 'उत्पादन सूची', 'change_password': 'पासवर्ड परिवर्तन', 'logout': 'लगआउट'
    },
}


def current_role(request):
    role = get_role(request.user) if hasattr(request, 'user') else None
    profile = DairyProfile.get_solo()
    lang = request.session.get('site_language') or request.COOKIES.get('django_language') or 'en'
    if lang not in NAV_LABELS:
        lang = 'en'
    unread_notifications = 0
    if getattr(request, 'user', None) and request.user.is_authenticated:
        try:
            unread_notifications = NotificationLog.objects.filter(Q(recipient=request.user) | Q(target_role=role)).exclude(status=NotificationLog.Status.READ).count()
        except Exception:
            unread_notifications = 0
    return {
        'current_role': role,
        'Role': Role,
        'dairy_profile': profile,
        'site_logo_url': profile.logo_url or static('img/mainlogo_square.png'),
        'bill_logo_url': profile.logo_url or static('img/mainlogo.png'),
        'current_language': lang,
        'L': NAV_LABELS[lang],
        'unread_notifications': unread_notifications,
    }
