# Build APK Without Installing Flutter Locally

Use this when Flutter installation gives errors on your computer. GitHub will build the APK online.

## Step 1: Upload this project to GitHub

1. Create a new private repository on GitHub.
2. Upload the full `dairy_management_system` folder to the repository.
3. Make sure this file exists in the repository:
   `.github/workflows/build-customer-apk.yml`

## Step 2: Run the APK build

1. Open your GitHub repository.
2. Go to **Actions**.
3. Select **Build Customer Android APK**.
4. Click **Run workflow**.
5. Enter your Django server URL:
   - For real phone on same Wi-Fi: `http://YOUR_COMPUTER_IP:8000`
   - Example: `http://192.168.1.25:8000`
   - For production VPS/domain: `https://yourdomain.com`
6. Click **Run workflow**.

## Step 3: Download APK

After the action finishes:

1. Open the completed workflow run.
2. Scroll to **Artifacts**.
3. Download **dairy-customer-app-release-apk**.
4. Extract the ZIP from GitHub.
5. Install `app-release.apk` on your Android phone.

## Important backend setup for real phone

Run Django using:

```bat
py -3 manage.py runserver 0.0.0.0:8000
```

Then use your computer IP in the workflow, not `127.0.0.1`.

To find your IP on Windows:

```bat
ipconfig
```

Look for `IPv4 Address`, for example `192.168.1.25`.

## Default customer login

Username: `customer1`

Password: `Customer@12345`
