import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:yaml/yaml.dart';

// FE-16: no personal profile and no recipe copy ship inside the app bundle.
// Every asset listed in pubspec.yaml is packaged into every build, flag or not.

void main() {
  final pubspec = loadYaml(File('pubspec.yaml').readAsStringSync()) as YamlMap;
  final assets = [
    for (final a in (pubspec['flutter'] as YamlMap)['assets'] as YamlList? ??
        YamlList())
      a.toString(),
  ];

  test('Given pubspec.yaml, Then no user profile or recipe asset is bundled',
      () {
    expect(assets, isNot(contains('assets/dev/user_profile.yaml')));
    expect(assets, isNot(contains('assets/dev/server_recipes.json')));
    expect(
      assets.where((a) => a.endsWith('.yaml') || a.endsWith('.yml')),
      isEmpty,
      reason: 'a bundled YAML would be a profile; profiles stay on the device',
    );
  });

  test('Given the removed assets, Then their files are gone too', () {
    expect(File('assets/dev/user_profile.yaml').existsSync(), isFalse);
    expect(File('assets/dev/server_recipes.json').existsSync(), isFalse);
  });

  test('Given every listed asset, Then the file exists', () {
    for (final a in assets) {
      expect(File(a).existsSync(), isTrue, reason: a);
    }
  });
}
