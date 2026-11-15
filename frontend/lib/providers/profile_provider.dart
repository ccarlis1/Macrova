import 'package:flutter/foundation.dart';

import '../models/micronutrient_defaults.dart';
import '../models/user_profile.dart';
import '../services/api_service.dart';
import '../services/storage_service.dart';

/// `GET /api/v1/micronutrient_defaults` for one demographic (BE-20).
typedef MicronutrientDefaultsFn = Future<MicronutrientDefaults> Function(
  String demographic,
);

class ProfileProvider extends ChangeNotifier {
  ProfileProvider({MicronutrientDefaultsFn? micronutrientDefaultsFn})
      : _defaultsFn = micronutrientDefaultsFn ??
            ((d) => ApiService.fetchMicronutrientDefaults(d));

  final MicronutrientDefaultsFn _defaultsFn;

  UserProfile _profile = const UserProfile();
  bool _loaded = false;

  /// Server defaults by demographic, as last fetched. Never written into
  /// [profile]: the Profile screen fills its fields from them, and only a save
  /// stores them.
  final Map<String, MicronutrientDefaults> _defaults = {};
  final Set<String> _defaultsLoading = {};
  final Map<String, String> _defaultsErrors = {};

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

  /// The fetched default for [demographic], or null (not fetched, failed, or
  /// not a supported demographic).
  MicronutrientDefaults? micronutrientDefaultsFor(String demographic) =>
      _defaults[demographic];

  bool micronutrientDefaultsLoading(String demographic) =>
      _defaultsLoading.contains(demographic);

  /// The last fetch error for [demographic], or null.
  String? micronutrientDefaultsError(String demographic) =>
      _defaultsErrors[demographic];

  /// Fetches the default goals for [demographic] (BE-20), once per
  /// demographic: a cached result returns without a request. "Not set" or an
  /// unsupported value fetches nothing and returns null. A failure returns
  /// null and is kept in [micronutrientDefaultsError]; calling again retries.
  Future<MicronutrientDefaults?> loadMicronutrientDefaults(
    String demographic,
  ) async {
    final d = UserProfile.normalizeDemographic(demographic);
    if (d.isEmpty) return null;
    final cached = _defaults[d];
    if (cached != null) return cached;
    if (_defaultsLoading.contains(d)) return null;

    _defaultsLoading.add(d);
    _defaultsErrors.remove(d);
    notifyListeners();
    try {
      final result = await _defaultsFn(d);
      _defaults[d] = result;
      return result;
    } catch (e) {
      _defaultsErrors[d] = e is ApiException ? e.message : e.toString();
      return null;
    } finally {
      _defaultsLoading.remove(d);
      notifyListeners();
    }
  }
}
