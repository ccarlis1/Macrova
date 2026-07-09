import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/providers/recipe_provider.dart';
import 'package:macrova/services/storage_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('RecipeProvider favorites', () {
    test(
      'Given a favorite toggle, When persisted and reloaded, Then isFavorite reflects it',
      () async {
        final provider = RecipeProvider(
          recipeSyncFn: (_) async => const [],
        );
        await provider.load();

        expect(provider.isFavorite('r1'), isFalse);
        await provider.toggleFavorite('r1');
        expect(provider.isFavorite('r1'), isTrue);

        final reloaded = RecipeProvider(
          recipeSyncFn: (_) async => const [],
        );
        await reloaded.load();
        expect(reloaded.isFavorite('r1'), isTrue);
        expect(await StorageService.loadFavoriteRecipeIds(), contains('r1'));
      },
    );

    test(
      'Given a favorited id, When toggled again, Then it is removed',
      () async {
        final provider = RecipeProvider(
          recipeSyncFn: (_) async => const [],
        );
        await provider.load();
        await provider.toggleFavorite('r1');
        await provider.toggleFavorite('r1');
        expect(provider.isFavorite('r1'), isFalse);
        expect(await StorageService.loadFavoriteRecipeIds(), isEmpty);
      },
    );
  });
}
