import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

import '../models/user_profile.dart';
import '../services/storage_service.dart';

/// Dev: `flutter run --dart-define=BUNDLE_USER_PROFILE=true`
const _bundleUserProfile = bool.fromEnvironment(
  'BUNDLE_USER_PROFILE',
  defaultValue: false,
);

const _bundledUserProfileAsset = 'assets/dev/user_profile.yaml';

class ProfileProvider extends ChangeNotifier {
  UserProfile _profile = const UserProfile();
  bool _loaded = false;

  UserProfile get profile => _profile;
  bool get loaded => _loaded;

  Future<void> load() async {
    final saved = await StorageService.loadProfile();
    if (saved != null) {
      _profile = saved;
    }
    _loaded = true;
    notifyListeners();
  }

  void updateProfile(UserProfile profile) {
    _profile = profile;
    notifyListeners();
  }

  Future<void> saveProfile(UserProfile profile) async {
    _profile = profile;
    await StorageService.saveProfile(profile);
    notifyListeners();
  }

  /// Loads [assets/dev/user_profile.yaml] (same shape as [config/user_profile.yaml]),
  /// replaces the in-memory profile, and persists to [StorageService] when enabled.
  Future<void> mergeBundledUserProfileIfEnabled() async {
    if (!_bundleUserProfile) return;
    try {
      final raw = await rootBundle.loadString(_bundledUserProfileAsset);
      final parsed = UserProfile.fromRepoYaml(raw);
      _profile = parsed;
      await StorageService.saveProfile(parsed);
      notifyListeners();
    } catch (e, st) {
      debugPrint('mergeBundledUserProfileIfEnabled: $e\n$st');
    }
  }
}
