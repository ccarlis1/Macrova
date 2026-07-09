import 'package:flutter/widgets.dart';

import '../models/models.dart';
import 'failure_panel.dart';

/// Maps structured [PlanFailure] / incomplete plan status into [FailurePanel] props.
class FailureViewModel {
  final String terminationCode;
  final String cause;
  final String? fixHint;

  const FailureViewModel({
    required this.terminationCode,
    required this.cause,
    this.fixHint,
  });

  factory FailureViewModel.fromPlanFailure(PlanFailure failure) {
    return FailureViewModel(
      terminationCode: failure.code,
      cause: failure.message,
      fixHint: failure.fixHint,
    );
  }

  /// Incomplete / non-success plan when [MealPlan.failures] is empty.
  factory FailureViewModel.incomplete({
    required String? planStatusMessage,
  }) {
    final msg = planStatusMessage?.trim();
    return FailureViewModel(
      terminationCode: 'Incomplete plan',
      cause: (msg != null && msg.isNotEmpty) ? msg : 'Incomplete plan',
    );
  }

  /// Prefer the first structured failure; otherwise incomplete messaging.
  factory FailureViewModel.fromMealPlan(MealPlan plan) {
    if (plan.failures.isNotEmpty) {
      return FailureViewModel.fromPlanFailure(plan.failures.first);
    }
    return FailureViewModel.incomplete(
      planStatusMessage: plan.planStatusMessage,
    );
  }

  FailurePanel toPanel({Key? key}) => FailurePanel(
        key: key,
        terminationCode: terminationCode,
        cause: cause,
        fixHint: fixHint,
      );
}
