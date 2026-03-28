import 'package:flutter/foundation.dart';

import '../models/recipe.dart';

/// One-shot action the library or shell consumes when opening the builder tab.
sealed class RecipeBuilderPendingAction {}

class RecipeBuilderPendingCreate extends RecipeBuilderPendingAction {}

class RecipeBuilderPendingEdit extends RecipeBuilderPendingAction {
  RecipeBuilderPendingEdit(this.recipe);
  final Recipe recipe;
}

/// Bridges [RecipeLibraryScreen] and [RecipeBuilderScreen] without relying on
/// ancestor state (they are siblings under [IndexedStack]).
class RecipeBuilderCoordinator extends ChangeNotifier {
  RecipeBuilderPendingAction? _pending;

  /// Returns and clears the pending action. Does not call [notifyListeners].
  RecipeBuilderPendingAction? takePendingAction() {
    final p = _pending;
    _pending = null;
    return p;
  }

  void openForEdit(Recipe recipe) {
    _pending = RecipeBuilderPendingEdit(recipe);
    notifyListeners();
  }

  void startCreate() {
    _pending = RecipeBuilderPendingCreate();
    notifyListeners();
  }
}
