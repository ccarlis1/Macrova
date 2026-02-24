# Flutter macOS Development Setup Guide

This guide documents everything you need to install and configure to get Flutter running on macOS, including all the tools required for Android, iOS, and web development.

---

## Prerequisites

### 1. Install Homebrew

Homebrew is a package manager for macOS. You'll use it to install most of the tools in this guide.

Open your terminal and run:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

---

## Step 1: Install Flutter

Flutter is the SDK (software development kit) that lets you build apps for iOS, Android, and web from a single codebase. Install it via Homebrew:

```bash
brew install --cask flutter
```

Verify the installation:

```bash
flutter --version
```

---

## Step 2: Install Ruby (Updated Version)

macOS comes with an old version of Ruby (2.6) built in, but CocoaPods (required for iOS) needs Ruby 3.0 or higher. Install a newer version via Homebrew:

```bash
brew install ruby
```

After installing, add the new Ruby to your PATH so your terminal uses it instead of the old system version. Add the following line to your `~/.zshrc` file:

```bash
export PATH="/opt/homebrew/opt/ruby/bin:/opt/homebrew/lib/ruby/gems/4.0.0/bin:$PATH"
```

Apply the changes:

```bash
source ~/.zshrc
```

Verify you now have the updated version:

```bash
ruby --version
```

It should show version 3.x or higher (not 2.6).

> **Why is this needed?** macOS ships with an outdated Ruby that can't run CocoaPods. Homebrew installs a modern version alongside it, and updating the PATH tells your terminal to use that one instead.

---

## Step 3: Install CocoaPods

CocoaPods is a package manager for iOS. Flutter uses it to manage iOS-specific dependencies and plugins. Install it **without** sudo (since you're using Homebrew's Ruby):

```bash
gem install cocoapods
```

Verify it installed:

```bash
pod --version
```

> **Important:** Do not use `sudo` here. Using sudo installs CocoaPods for the old system Ruby, not the Homebrew one, so Flutter won't be able to find it.

---

## Step 4: Install Xcode

Xcode contains Apple's build tools, which are required to compile and run apps on iOS. Flutter cannot build iOS apps without it.

1. Download **Xcode** from the Mac App Store (search "Xcode")
2. Once installed, open Xcode and agree to the license agreement
3. Install the iOS Simulator: open Xcode → **Settings** → **Components** → click **Get** next to the iOS platform

> **Note:** You don't need to write code in Xcode. It just needs to be installed so Flutter can access its build tools.

---

## Step 5: Install Android Studio

Android Studio contains the Android SDK — the tools Flutter needs to build and package apps for Android devices. Like Xcode, you don't need to code in it, it just needs to be installed.

1. Download **Android Studio** from [developer.android.com/studio](https://developer.android.com/studio)
2. Open Android Studio and follow the setup wizard — it will automatically install the Android SDK
3. Once set up, install the Android Command Line Tools:
   - Go to **Settings** → **Languages & Frameworks** → **Android SDK**
   - Click the **SDK Tools** tab
   - Check **Android SDK Command-line Tools (latest)**
   - Click **Apply** and let it download
4. Accept the Android licenses by running:

```bash
flutter doctor --android-licenses
```

Press `y` to accept each license.

> **Why Android Studio AND Xcode?** Flutter writes your app code, but hands off the final build process to each platform's native tools. Flutter → Xcode → iOS app. Flutter → Android SDK → Android app. Flutter → Chrome → Web app (no extra tools needed for web).

---

## Step 6: Install Flutter & Dart Extensions in Cursor

Cursor is built on VS Code, so you can install extensions the same way:

1. Open the Extensions panel with `Cmd + Shift + X`
2. Search for **Flutter** and install the extension by Dart Code
3. Search for **Dart** and install that extension too

These give you syntax highlighting, autocomplete, debugging, and the ability to run Flutter from within Cursor.

---

## Step 7: Verify Everything with Flutter Doctor

Run this command to check the status of your full setup:

```bash
flutter doctor
```

You should see checkmarks next to Flutter, Android toolchain, Xcode, Chrome, and Connected device. Fix any remaining issues based on the output.

---

## Creating Your First Flutter App

Navigate to the folder where you keep your projects and run:

```bash
flutter create my_app
cd my_app
```

Run the app in Chrome (works immediately, no extra setup):

```bash
flutter run -d chrome
```

Run on iOS Simulator:

```bash
flutter run -d ios
```

Run on Android Emulator (set one up via Android Studio's Device Manager first):

```bash
flutter run -d android
```

---

## Working with a Python Backend

Your Flutter frontend and Python backend are completely separate. They communicate over an API (REST or GraphQL). Keep them in separate folders or repos:

```
my-project/
├── backend/        ← Your Python backend
│   └── venv/       ← Python virtual environment
└── frontend/       ← Your Flutter app
```

### Managing Your Python Virtual Environment

Activate your Python venv when working on the backend:

```bash
source venv/bin/activate
```

Deactivate when you're done or when running Flutter/Ruby commands:

```bash
deactivate
```

> **Important:** Your Python venv only manages Python packages. Ruby, CocoaPods, and Flutter are system-level tools and should be run outside the venv.

---

## Quick Reference

| Command | What it does |
|---|---|
| `flutter doctor` | Check your setup status |
| `flutter create app_name` | Create a new Flutter project |
| `flutter run -d chrome` | Run app in browser |
| `flutter run -d ios` | Run app on iOS Simulator |
| `flutter run -d android` | Run app on Android Emulator |
| `pod --version` | Check if CocoaPods is installed |
| `ruby --version` | Check Ruby version (should be 3.x+) |
| `source venv/bin/activate` | Activate Python virtual environment |
| `deactivate` | Deactivate Python virtual environment |

---

## Troubleshooting

**`ruby --version` still shows 2.6 after installing via Homebrew**
Your PATH hasn't been updated. Make sure you added the export line to `~/.zshrc` and ran `source ~/.zshrc`.

**CocoaPods installed but Flutter doctor doesn't see it**
You may have installed it with `sudo` (system Ruby). Reinstall without sudo after updating your PATH to use Homebrew Ruby: `gem install cocoapods`

**`flutter doctor --android-licenses` says Android sdkmanager not found**
You need to install the Command Line Tools in Android Studio: Settings → Languages & Frameworks → Android SDK → SDK Tools tab → check Android SDK Command-line Tools.

**Terminal freezes during `gem install cocoapods`**
It's not frozen — it can take 5–10 minutes. Wait for the "Successfully installed" message.
