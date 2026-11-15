import 'package:flutter/foundation.dart';

import '../models/user_profile.dart';
import '../services/storage_service.dart';

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
}
