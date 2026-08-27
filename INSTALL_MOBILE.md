# Install Clinic System on Mobile Devices

## Overview

The Clinic System is a **Progressive Web App (PWA)** that can be installed on Android, iOS, and desktop devices. Once installed, it works like a native app - you can launch it from your home screen and it works offline.

## Features When Installed

- 🚀 **Fast access** - Launch from home screen like a native app
- 📴 **Offline mode** - Continue working without internet
- 🔔 **App-like experience** - No browser UI, full-screen mode
- 💾 **Local data** - Data stored on device, syncs when online
- 📱 **Touch-optimized** - Designed for mobile interaction

## Installation Instructions

### ⚠️ Important: You MUST use HTTPS

Mobile browsers **block the install prompt and offline mode on plain `http://`**
(except on `localhost`). If you open `http://<server-ip>:8000/` on your phone,
no install banner will ever appear and the app will not work offline.

**Start the server with HTTPS instead:**

```bat
run_https.bat
```

This serves the app at `https://0.0.0.0:8000/` using the included dev certificate.

### Android (Chrome/Edge)

1. Start the server with `run_https.bat`
2. Open Chrome on your Android device
3. Navigate to: `https://10.36.169.35:8000/` (use your server's IP)
4. You will see a certificate warning — tap **Advanced → Proceed** (safe on your own clinic network)
5. Browse a few pages (dashboard, patient search) so they are cached for offline use
6. Look for the install banner at the bottom (appears after ~3 seconds), or menu → **"Add to Home screen" / "Install app"**
7. Tap "Install"
8. App icon will appear on home screen

### iOS (Safari)

1. Start the server with `run_https.bat`
2. Open Safari on iPhone/iPad
3. Navigate to: `https://10.36.169.35:8000/`
4. Accept the certificate warning (Show Details → visit this website)
5. Tap Share button (square with arrow)
6. Scroll down and tap "Add to Home Screen"
7. Tap "Add"
8. App icon appears on home screen

**Note:** iOS has limited PWA support. App runs in Safari's WebKit engine.

### Desktop (Chrome/Edge)

1. Open Chrome or Edge
2. Navigate to: `http://localhost:8000/`
3. Look for install icon (⊕) in address bar
4. Click "Install"
5. App opens in its own window


## Requirements

### HTTPS (Required for Production)

⚠️ PWAs require HTTPS except on localhost.

- **localhost** - Works without HTTPS (development only)
- **Local network** - May work on some Android browsers  
- **Internet** - Must use HTTPS (SSL certificate required)

### Server Configuration

```python
# settings.py
ALLOWED_HOSTS = ['*']  # Or specific IPs in production

# Production with HTTPS:
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

## Troubleshooting

### "Add to Home Screen" not available
- Use Chrome (Android) or Safari (iOS)
- Ensure HTTPS (except localhost)
- Clear browser cache and reload
- Check service worker in browser console

### App doesn't work offline
- Open app while online first (to cache assets)
- Check console for service worker errors
- Visit multiple pages to cache them
- Clear old service workers in browser settings

### Install prompt doesn't appear
- Banner appears after 3 seconds, wait longer
- **iPhone/iPad:** Safari has NO automatic install prompt — use Share → "Add to
  Home Screen" (an on-screen guide now appears on iOS).
- **Use a STABLE HTTPS address.** The quick `*.trycloudflare.com` tunnel changes
  every restart, resetting install. See `SETUP_STABLE_TUNNEL.md`.
- Check console for PWA errors
- Verify manifest.json accessible
- Ensure icons exist in /static/pwa/

## Testing PWA Features

### Verify Installation
1. Open DevTools (F12) → Application tab
2. Check Service Workers (should show active)
3. Check Manifest (shows app details)
4. Check Storage (shows cached assets)

### Test Offline Mode
1. Install app and open it
2. Navigate through pages
3. Turn off WiFi/mobile data
4. Refresh - app should load
5. Try basic functions offline

## PWA Icons

**Current:** Placeholder icons (green background with "CS" text)

**For production:**
1. Design professional icons (512x512px minimum)
2. Replace files in: `static/pwa/icon-*.png`
3. Required sizes: 72, 96, 128, 144, 152, 192, 384, 512

**Icon design tips:**
- Use clinic logo or medical symbol
- Ensure visibility on light/dark backgrounds
- Keep it simple and recognizable
- Use brand colors

## Browser Compatibility

| Browser | Android | iOS | Desktop | Support |
|---------|---------|-----|---------|---------|
| Chrome  | ✅      | N/A | ✅      | ✅ Full |
| Edge    | ✅      | N/A | ✅      | ✅ Full |
| Safari  | N/A     | ✅  | N/A     | ⚠️ Partial |
| Firefox | ✅      | N/A | ✅      | ⚠️ Limited |

**Recommended:** Chrome on Android, Safari on iOS.

## Managing the App

### Update
- Close app completely
- Clear cache or uninstall/reinstall
- Or wait for auto-update (1-2 hours)

### Uninstall
- **Android:** Long-press icon → Remove
- **iOS:** Long-press icon → Remove App → Delete
- **Desktop:** Right-click → Remove or uninstall

## Next Steps

After installation:
1. Login with staff credentials
2. Test core functions (register, search, create invoice)
3. Go offline and verify app works
4. Train staff on mobile app usage

---

**Note:** Always use strong passwords and log out when finished. For support, check browser console for errors and verify HTTPS is configured.
