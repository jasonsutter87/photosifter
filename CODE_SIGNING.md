# Code Signing Guide

How to sign PhotoSifter for distribution without developer warnings.

## macOS

**Requirement**: Apple Developer Program ($99/year)

1. Enroll at [developer.apple.com](https://developer.apple.com)
2. Create a "Developer ID Application" certificate in Certificates, Identifiers & Profiles
3. Sign your app:
   ```bash
   codesign --deep --force --sign "Developer ID Application: Your Name (TEAMID)" PhotoSifter.app
   ```
4. Notarize (required for macOS 10.15+):
   ```bash
   xcrun notarytool submit PhotoSifter.zip --apple-id you@email.com --team-id TEAMID --password APP_SPECIFIC_PASSWORD
   xcrun stapler staple PhotoSifter.app
   ```

## Windows

**Requirement**: Code Signing Certificate

| Provider | Type | Price | SmartScreen |
|----------|------|-------|-------------|
| Certum | OV | ~$30/yr | Builds trust slowly |
| SSL.com | OV | ~$70/yr | Builds trust slowly |
| DigiCert/Sectigo | EV | ~$300/yr | Instant trust |

Sign with signtool:
```bash
signtool sign /tr http://timestamp.digicert.com /td sha256 /fd sha256 /a PhotoSifter.exe
```

## Linux

No signing typically needed. Users install via package managers which handle trust.

## Unsigned Distribution

If skipping signing initially, instruct users:

- **macOS**: Right-click the app → Open → Click "Open" in the dialog
- **Windows**: Click "More info" → "Run anyway"
