# Flutter Customer App

This is the customer mobile app shell required by the Dairy Management System PDF. It connects to the Django backend APIs:

- `/api/login/`
- `/api/customer/profile/`
- `/api/products/`
- `/api/customer/purchases/`
- `/api/bills/`
- `/api/bill/<id>/`
- `/api/notifications/`

## Run

1. Install Flutter.
2. Start Django: `python manage.py runserver 0.0.0.0:8000`.
3. From this folder run:

```bash
flutter pub get
flutter run
```

For Android emulator the app uses `http://10.0.2.2:8000`. For a real phone, replace `baseUrl` in `lib/main.dart` with `http://YOUR_SERVER_IP:8000`.
