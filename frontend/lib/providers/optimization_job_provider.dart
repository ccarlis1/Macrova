import 'dart:async';

import 'package:flutter/widgets.dart';

import '../models/optimize_cart_job_status.dart';
import '../services/api_service.dart';

/// Polls async grocery optimize-cart jobs with adaptive interval (2s → 4s after 30s).
class OptimizationJobProvider extends ChangeNotifier with WidgetsBindingObserver {
  OptimizationJobProvider() {
    WidgetsBinding.instance.addObserver(this);
  }

  String? _activeJobId;
  Timer? _pollTimer;
  DateTime? _pollStartTime;
  OptimizeCartJobStatus? _status;
  ApiException? _pollException;
  Map<String, dynamic>? _retryBody;
  String? _retryMealPlanId;
  bool _starting = false;

  OptimizeCartJobStatus? get status => _status;
  ApiException? get pollException => _pollException;
  bool get isPolling =>
      _activeJobId != null && !(_status?.isTerminal ?? false);
  bool get isBusy => _starting || isPolling;

  Map<String, dynamic>? get retrySnapshotBody => _retryBody;
  String? get retryMealPlanId => _retryMealPlanId;

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed && _activeJobId != null) {
      unawaited(_pollOnce());
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _pollTimer?.cancel();
    super.dispose();
  }

  /// Registers meal plan, enqueues optimization, and starts polling.
  Future<void> startOptimizeCart({
    required Map<String, dynamic> groceryBody,
    required String mealPlanId,
    String mode = 'balanced',
    int maxStores = 4,
  }) async {
    _cancelPollTimer();
    _retryBody = Map<String, dynamic>.from(groceryBody);
    _retryMealPlanId = mealPlanId;
    _status = null;
    _pollException = null;
    _starting = true;
    notifyListeners();

    try {
      await ApiService.registerMealPlanSnapshot(groceryBody);
      final jobId = await ApiService.startOptimizeCartJob(
        mealPlanId: mealPlanId,
        mode: mode,
        maxStores: maxStores,
      );
      _activeJobId = jobId;
      _pollStartTime = DateTime.now();
      notifyListeners();
      await _pollOnce();
      if (_activeJobId != null && !(_status?.isTerminal ?? true)) {
        _scheduleFollowUpPoll();
      }
    } finally {
      _starting = false;
      notifyListeners();
    }
  }

  /// Submits the same registered payload as a new job (after failure or user retry).
  Future<void> retry() async {
    final body = _retryBody;
    final id = _retryMealPlanId;
    if (body == null || id == null) return;
    await startOptimizeCart(groceryBody: body, mealPlanId: id);
  }

  void dismissUi() {
    _status = null;
    _pollException = null;
    _cancelPollTimer();
    _activeJobId = null;
    notifyListeners();
  }

  void _cancelPollTimer() {
    _pollTimer?.cancel();
    _pollTimer = null;
  }

  Future<void> _pollOnce() async {
    final id = _activeJobId;
    if (id == null) return;
    try {
      final s = await ApiService.getOptimizeCartJob(id);
      _status = s;
      _pollException = null;
      if (s.isTerminal) {
        _activeJobId = null;
        _cancelPollTimer();
      }
      notifyListeners();
    } on ApiException catch (e) {
      _pollException = e;
      if (e.statusCode == 404) {
        _activeJobId = null;
      }
      notifyListeners();
    } catch (e) {
      _pollException = ApiException(
        statusCode: 0,
        code: 'POLL_ERROR',
        message: e.toString(),
      );
      notifyListeners();
    }
  }

  void _scheduleFollowUpPoll() {
    _cancelPollTimer();
    if (_activeJobId == null) return;
    final started = _pollStartTime ?? DateTime.now();
    final elapsedSec = DateTime.now().difference(started).inSeconds;
    final sec = elapsedSec >= 30 ? 4 : 2;
    _pollTimer = Timer(Duration(seconds: sec), () async {
      await _pollOnce();
      if (_activeJobId != null && !(_status?.isTerminal ?? true)) {
        _scheduleFollowUpPoll();
      }
    });
  }
}
