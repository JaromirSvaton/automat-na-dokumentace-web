# Google OAuth Setup Guide

This guide explains how to configure Google OAuth authentication for the Elevator Documentation Generator app on Streamlit Cloud.

## Prerequisites

- A Google account
- Access to [Google Cloud Console](https://console.cloud.google.com/)
- A deployed Streamlit Cloud app (or plans to deploy)

---

## Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **"Select a project"** at the top
3. Click **"New Project"**
4. Fill in:
   - **Project name**: `elevator-docs-generator` (or your choice)
   - **Location**: Personal or your organization
5. Click **"Create"**
6. Wait for the project to be created, then select it

> **Note**: Your Project ID will be shown. Keep this for reference.

---

## Step 2: Enable the Google Drive API

1. In the left sidebar, go to **APIs & Services** → **Library**
2. In the search bar, type **"Google Drive API"**
3. Click on **"Google Drive API"** (should be the first result)
4. Click **"Enable"**
5. Wait for the API to be enabled

---

## Step 3: Configure the OAuth Consent Screen

1. Go to **APIs & Services** → **OAuth consent screen**
2. Click **"Create"**
3. Choose **"External"** and click **"Create"**
4. Fill in the required fields:

   | Field | Value |
   |-------|-------|
   | App name | `Elevator Documentation Generator` |
   | User support email | Your email address |
   | Developer contact information | Your email address |

5. Click **"Save and Continue"**
6. On the **Scopes** page:
   - Click **"Add or Remove Scopes"**
   - Check the box for `../auth/drive.readonly`
   - Click **"Save and Continue"**
7. On the **Test users** page:
   - Click **"Add Users"**
   - Enter your Google email address (and any other test users)
   - Click **"Add"**
   - Click **"Save and Continue"**

> **Important**: Without test users, only users in the same Google organization can access the app. For personal/small team use, add test users.

---

## Step 4: Create OAuth Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **"Create Credentials"**
3. Select **"OAuth client ID"**
4. For Application type, select **"Web application"**
5. Name it: `Streamlit App`
6. In **Authorized redirect URIs**, add:
   ```
   https://streamlit.io/oauth_callback
   ```
7. Click **"Create"**
8. A dialog will appear with your **Client ID** and **Client Secret**
9. Copy both values and save them securely (you'll need them for Streamlit secrets)

---

## Step 5: Deploy to Streamlit Cloud (if not already deployed)

1. Push your code to GitHub
2. Go to [share.streamlit.app](https://share.streamlit.app)
3. Click **"New app"**
4. Select your repository and branch
5. Click **"Deploy"**

---

## Step 6: Add Secrets to Streamlit Cloud

1. Go to your deployed app on Streamlit Cloud
2. Click the **"Settings"** gear icon (top right)
3. Click the **"Secrets"** tab
4. Add the following:

```toml
[auth]
client_id = "YOUR_CLIENT_ID_HERE"
client_secret = "YOUR_CLIENT_SECRET_HERE"
```

5. Click **"Save"**
6. The app will automatically restart with the new secrets

---

## Step 7: Test the Authentication

1. Open your deployed app
2. You should see a **"Přihlásit se přes Google"** (Login with Google) button in the sidebar
3. Click it
4. Complete the Google sign-in flow
5. After successful login, the sidebar should show your email

---

## Troubleshooting

### "App isn't verified" warning
- This is normal for apps in testing mode
- Click "Advanced" → "Go to [app name] (unsafe)"
- This is only needed for test users during development

### "Sign in with Google" button not visible
- Check that secrets are configured correctly
- Verify the `[auth]` section exists in secrets.toml

### Users can't access the app
- Make sure their emails are added as test users
- For production, you'll need to submit the app for verification

### Authentication keeps asking for login
- Check that Client ID and Client Secret are correct
- Ensure the OAuth consent screen is properly configured

---

## Security Notes

- Never commit OAuth secrets to git
- Keep Client ID and Client Secret confidential
- The app works without Google login (local file upload is always available)
- Google Drive integration is optional

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      User's Browser                          │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Streamlit Cloud                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                   app.py                              │   │
│  │  ┌─────────────┐    ┌────────────────────────────┐  │   │
│  │  │ st.login() │───▶│ Google OAuth 2.0 Flow      │  │   │
│  │  └─────────────┘    └────────────────────────────┘  │   │
│  │                              │                       │   │
│  │                              ▼                       │   │
│  │  ┌───────────────────────────────────────────────┐  │   │
│  │  │         Google Drive Integration             │  │   │
│  │  │  - Browse files                               │  │   │
│  │  │  - Download files                             │  │   │
│  │  └───────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   Google Cloud                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │            Google Drive API                          │   │
│  │  - OAuth 2.0 Authentication                         │   │
│  │  - File listing and download                         │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Quick Reference

| Item | Where to find |
|------|---------------|
| Google Cloud Console | console.cloud.google.com |
| Enable APIs | APIs & Services → Library |
| OAuth settings | APIs & Services → OAuth consent screen |
| Credentials | APIs & Services → Credentials |
| Streamlit secrets | share.streamlit.app → Settings → Secrets |

---

## Need Help?

If you encounter issues:

1. Check the [Streamlit authentication docs](https://docs.streamlit.io/develop/authentication)
2. Check the [Google Drive API docs](https://developers.google.com/drive/api/guides/about-files)
3. Review the app logs in Streamlit Cloud for error messages
