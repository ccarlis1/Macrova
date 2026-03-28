import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../models/user_profile.dart';
import '../../providers/profile_provider.dart';
import '../../services/api_service.dart';

/// Gate for agentic API usage: local credential shape + **server** `/api/v1/llm/status`.
///
/// The API never receives the profile LLM key; it uses `LLM_API_KEY` / `LLM_ENABLED` in its own
/// environment. [validate] and [loadFromProfile] confirm the server reports `enabled: true`.
class LlmConfigProvider extends ChangeNotifier {
  LlmConfigProvider(this._profile);

  final ProfileProvider _profile;

  static const supportedProviderIds = ['openai_compatible'];

  static const List<(String id, String label)> supportedProviders = [
    ('openai_compatible', 'OpenAI-compatible'),
  ];

  static bool isAssistedPlanningMode(String? mode) {
    if (mode == null || mode.isEmpty) return false;
    return mode == 'assisted' ||
        mode == 'assisted_cached' ||
        mode == 'assisted_live';
  }

  bool _llmReady = false;
  bool _validating = false;
  String? _lastValidationError;
  DateTime? _validatedAt;
  int? _validatedFingerprint;

  bool get llmReady => _llmReady;
  bool get validating => _validating;
  String? get lastValidationError => _lastValidationError;
  DateTime? get validatedAt => _validatedAt;

  int _fingerprint(UserProfile p) => Object.hash(
        p.llmProvider.trim().toLowerCase(),
        p.llmApiKey.trim(),
      );

  /// Public so UI can preview errors before calling [validate].
  bool validateCredentialsLocally(UserProfile p) {
    final key = p.llmApiKey.trim();
    final prov = p.llmProvider.trim().toLowerCase();
    if (key.length < 12) return false;
    if (!supportedProviderIds.contains(prov)) return false;
    return true;
  }

  Future<void> loadFromProfile() async {
    final prefs = await SharedPreferences.getInstance();
    final fp = prefs.getInt(_kFpKey);
    final atMs = prefs.getInt(_kAtKey);
    final p = _profile.profile;
    final cur = _fingerprint(p);
    if (fp != null && fp == cur && validateCredentialsLocally(p)) {
      _validatedFingerprint = fp;
      _validatedAt =
          atMs != null ? DateTime.fromMillisecondsSinceEpoch(atMs) : null;
      await _syncReadyWithServer();
    } else {
      _llmReady = false;
      _validatedFingerprint = null;
      _validatedAt = null;
      _lastValidationError = null;
    }
    notifyListeners();
  }

  Future<void> _syncReadyWithServer() async {
    try {
      final enabled = await ApiService.fetchLlmServerEnabled();
      _llmReady = enabled;
      if (!enabled) {
        _lastValidationError =
            'This API has no LLM configured. Set LLM_API_KEY (or LLM_ENABLED=true) in the '
            'environment where you run the server—not in Flutter alone. Your Profile key is '
            'not sent to the API.';
        await _clearPrefs();
        _validatedFingerprint = null;
        _validatedAt = null;
      } else {
        _lastValidationError = null;
      }
    } on ApiException catch (e) {
      _llmReady = false;
      _lastValidationError =
          'Could not read LLM status from the API (${e.message}). '
          'Is the server running at ${ApiService.baseUrl}?';
      await _clearPrefs();
      _validatedFingerprint = null;
      _validatedAt = null;
    } catch (e) {
      _llmReady = false;
      _lastValidationError = 'Could not reach the API: $e';
      await _clearPrefs();
      _validatedFingerprint = null;
      _validatedAt = null;
    }
  }

  /// Call when [ProfileProvider] may have changed without going through validate.
  void syncCredentialsFromProfile() {
    final p = _profile.profile;
    final cur = _fingerprint(p);
    if (_validatedFingerprint != null && cur != _validatedFingerprint) {
      _llmReady = false;
      _validatedFingerprint = null;
      _validatedAt = null;
      notifyListeners();
    }
  }

  Future<void> validate() async {
    _validating = true;
    _lastValidationError = null;
    notifyListeners();
    final p = _profile.profile;
    try {
      if (!validateCredentialsLocally(p)) {
        _llmReady = false;
        _lastValidationError =
            'Use a supported provider and an API key with at least 12 characters.';
        await _clearPrefs();
        return;
      }

      final enabled = await ApiService.fetchLlmServerEnabled();
      if (!enabled) {
        _llmReady = false;
        _validatedFingerprint = null;
        _validatedAt = null;
        _lastValidationError =
            'Server reports LLM is off. Add LLM_API_KEY to the same .env / process that runs '
            '`uvicorn` (see repo .env). The Profile field documents your key for your own '
            'reference; the API does not use it.';
        await _clearPrefs();
        return;
      }

      final fp = _fingerprint(p);
      final prefs = await SharedPreferences.getInstance();
      await prefs.setInt(_kFpKey, fp);
      await prefs.setInt(
        _kAtKey,
        DateTime.now().millisecondsSinceEpoch,
      );
      _llmReady = true;
      _validatedFingerprint = fp;
      _validatedAt = DateTime.now();
      _lastValidationError = null;
    } on ApiException catch (e) {
      _llmReady = false;
      _validatedFingerprint = null;
      _validatedAt = null;
      _lastValidationError =
          'Could not verify LLM with the server (${e.message}). '
          'Check API_BASE_URL / dart-define and that the API is running.';
      await _clearPrefs();
    } catch (e) {
      _llmReady = false;
      _validatedFingerprint = null;
      _validatedAt = null;
      _lastValidationError = 'Could not reach the API: $e';
      await _clearPrefs();
    } finally {
      _validating = false;
      notifyListeners();
    }
  }

  Future<void> _clearPrefs() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_kFpKey);
    await prefs.remove(_kAtKey);
  }

  void onCredentialsChanged() {
    _llmReady = false;
    _validatedFingerprint = null;
    _validatedAt = null;
    notifyListeners();
  }

  /// First failing agentic call should clear the rail so the user re-validates.
  void revokeReady(String message) {
    _llmReady = false;
    _validatedFingerprint = null;
    _validatedAt = null;
    _lastValidationError = message;
    unawaited(_clearPrefs());
    notifyListeners();
  }

  static const _kFpKey = 'llm_gate_fingerprint';
  static const _kAtKey = 'llm_gate_validated_at_ms';
}
