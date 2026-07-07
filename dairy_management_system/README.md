# Dairy Management System

A Django + Bootstrap web system developed from the uploaded requirement PDF. It now includes the complete first working version of the required Admin, Seller, Customer, MIS, backup, activity log, bilingual UI switch, mobile API, and Flutter customer app modules.

## Default login after seeding

| Role | Username | Password |
|---|---|---|
| Admin | `admin` | `Admin@12345` |
| Seller | `seller1` | `Seller@12345` |
| Customer | `customer1` | `Customer@12345` |

## Quick start on Windows

1. Extract this ZIP.
2. Open the extracted folder.
3. Double-click `run_windows.bat`.
4. Open: `http://127.0.0.1:8000/`

The batch file creates a virtual environment, installs requirements, migrates the database, seeds sample data, and starts the server.

## Fix: Python was not found / pip is not recognized

Install Python 3.11 or newer and tick **Add python.exe to PATH** during installation. If Windows opens the Microsoft Store message, disable app aliases:

`Settings > Apps > Advanced app settings > App execution aliases > turn off python.exe and python3.exe`

## Manual start

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver 0.0.0.0:8000
```

## Requirements completed from the PDF

### Technology and setup

- Django backend.
- Bootstrap 5 web templates.
- SQLite default for easy local testing.
- PostgreSQL configuration ready through `.env`.
- PDF export using ReportLab.
- Excel export using OpenPyXL.
- Mobile customer app shell using Flutter.
- Simple token-based API for mobile app connection.
- English / Nepali language switch in the web UI.

### Admin module

Admin can manage:

- Dairy profile: name, address, PAN, contact, email, logo URL, bill header/footer, terms.
- Users and roles: Admin, Seller, Customer.
- Shops / branches.
- Units / metric system.
- Products with product code, unit, selling price, cost price, category, low-stock threshold, status.
- Daily product receiving.
- Product batches with automatic batch numbers.
- Customers.
- Payment methods.
- Bill format / invoice template.
- Website / mobile system settings.
- Notifications.
- Sales and bills.
- MIS reports.
- Activity logs.
- Backup and restore.

### Seller module

Seller can:

- View seller dashboard.
- See today’s sales.
- See available batches.
- Search product by product name or batch number.
- Use QR/barcode scanner text input through the same search field.
- Register customers during billing workflow.
- Select shop / branch.
- Generate bills.
- Select payment method added by admin.
- Apply discount.
- Automatically deduct stock after sale.
- View own bills.

### Customer web module

Customer can:

- Login.
- View profile.
- Update basic profile.
- Change password.
- View available products.
- View purchase history.
- View bill list.
- View payment status.
- Download PDF invoice.
- View notifications.

### Billing and inventory

- Automatic batch number format: `PRODUCTCODE-YYYYMMDD-001`.
- Batch-wise stock receiving.
- Batch-wise stock deduction after sale.
- Customer purchase history updates automatically.
- Sales report updates automatically.
- Payment report updates automatically.
- Due payment calculation.
- Logo appears in website, sidebar, bill page, and PDF invoice.

### MIS reports

Open **MIS Reports** from admin sidebar. Included reports:

- Daily Sales Report.
- Product-wise Sales Report.
- Batch-wise Report.
- Customer-wise Report.
- Seller-wise Report.
- Shop-wise Report.
- Payment Method Report.
- Stock Report.
- Low Stock Report.
- Expired Product Report.
- Monthly Sales Report.
- Profit/Loss Report.
- Due Payment Report.

Each MIS report supports:

- Date filter.
- Product filter.
- Customer filter.
- Seller filter.
- Shop filter.
- Payment method filter.
- Print.
- Export Excel.
- Export PDF.
- Save report configuration.

### Activity logs

The system tracks:

- Create.
- Update.
- Delete.
- Download.
- Upload.
- Backup.
- Restore.
- Bill PDF download.
- Sale generation.

Activity logs can be filtered and exported as CSV.

### Backup / restore

Admin can:

- Download current database backup.
- Create saved backup.
- Upload `.sqlite3` or `.db` backup.
- Restore uploaded backup.
- Download saved backups.

A safety copy is created before restore.

### Mobile API endpoints

The Django backend includes the mobile API endpoints listed in the PDF:

- `POST /api/login/`
- `GET /api/customer/profile/`
- `GET /api/products/`
- `GET /api/customer/purchases/`
- `GET /api/bills/`
- `GET /api/bill/<id>/`
- `GET /api/notifications/`

Login returns a token. Send the token in headers:

```text
Authorization: Token YOUR_TOKEN_HERE
```

### Flutter customer app

A Flutter customer app starter is included in:

```text
flutter_customer_app/
```

It includes:

- Login screen.
- Language switch.
- Product list.
- Purchase history.
- Bill list.
- Notification screen.
- Profile screen.
- API connection with the Django backend.

## PostgreSQL production setup

The system runs with SQLite first for quick testing. To switch to PostgreSQL, create `.env`:

```env
DJANGO_SECRET_KEY=change-this-secret-key
DJANGO_DEBUG=True
DB_ENGINE=postgres
DB_NAME=dairy_management_db
DB_USER=dairy_user
DB_PASSWORD=StrongPassword@123
DB_HOST=localhost
DB_PORT=5432
```

Then run:

```bash
python manage.py migrate
python manage.py seed_demo
```

## Included important folders

```text
core/                  Django app
static/                CSS and logo assets
backups/               Saved database backups
flutter_customer_app/  Flutter customer mobile app shell
run_windows.bat        Windows launcher
INSTALL_PYTHON_WINDOWS.txt
```

## Latest Update: Monthly Customer Billing + Nepali Fiscal-Year Invoice Numbers

This package now includes the requested changes:

1. **Customer profile and customer login**
   - Admin can create customer login users from **Users > Add User**.
   - Seller/Admin can also tick **Create customer login account** while adding a customer.
   - Customer can log in, update profile, change password, view bills, and download invoices.

2. **Daily customer product entry**
   - Use **Daily Customer Products > Add Daily Product** to add milk/curd/etc. supplied to a regular customer every day.
   - Stock is deducted immediately from the selected batch.
   - Daily entries remain **Unbilled** until a monthly bill is generated.

3. **Monthly bill generation**
   - Use **Monthly Customer Search** to find daily-basis customers who pay monthly.
   - Use **Generate Monthly Bill** to combine unbilled daily entries into one invoice for a selected month/period.
   - Monthly invoices show the billing period on the bill.

4. **Nepali fiscal-year invoice number**
   - Admin can add/manage fiscal years from **Fiscal Years**.
   - Invoice number format uses the fiscal year, for example: `INV-2082-83-0001`.
   - If no fiscal year is added, the system automatically creates a current Nepali fiscal year approximation.

5. **Seller monthly report**
   - Seller can open **Monthly Report / MIS Reports**.
   - Seller reports are automatically limited to the seller's own sales.
   - Admin can view all sellers' reports.

6. **Payment method image on bill**
   - Admin can upload a QR/payment image in **Payment Methods**.
   - If uploaded, the payment image appears on the top-right side of the bill and PDF invoice.


## Latest Bill Layout Update
- Invoice totals now show: Overall Discount, Paid, Total, Return, and Due.
- Return amount is automatically calculated when the paid amount is greater than the total bill amount.
