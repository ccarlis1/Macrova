import 'package:flutter/material.dart';

import 'tokens.dart';

/// Builds [ThemeData] from [MacrovaTokens] for light and dark modes.
abstract final class AppTheme {
  static ThemeData get light => _build(MacrovaTokens.light);

  static ThemeData get dark => _build(MacrovaTokens.dark);

  static ThemeData _build(MacrovaTokens tokens) {
    final colorScheme = _colorScheme(tokens);
    final textTheme = _textTheme(tokens);

    return ThemeData(
      useMaterial3: true,
      brightness: tokens.isDark ? Brightness.dark : Brightness.light,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: tokens.canvas,
      textTheme: textTheme,
      extensions: [tokens],
      appBarTheme: AppBarTheme(
        elevation: 0,
        scrolledUnderElevation: 0,
        backgroundColor: tokens.stickyBar,
        foregroundColor: tokens.inkPrimary,
        surfaceTintColor: Colors.transparent,
        titleTextStyle: MacrovaTypography.titleSm(tokens.inkPrimary),
      ),
      cardTheme: CardThemeData(
        elevation: 0,
        margin: EdgeInsets.zero,
        color: tokens.isDark
            ? MacrovaColorsDark.surfaceCard
            : MacrovaColors.surfaceCard,
        shape: RoundedRectangleBorder(
          borderRadius: MacrovaRadius.borderMd,
          side: BorderSide(color: tokens.lineDefault),
        ),
      ),
      dividerTheme: DividerThemeData(
        color: tokens.lineSoft,
        thickness: 1,
        space: 1,
      ),
      inputDecorationTheme: InputDecorationTheme(
        isDense: true,
        filled: true,
        fillColor: tokens.isDark
            ? MacrovaColorsDark.surfaceCard
            : MacrovaColors.surfaceCard,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: MacrovaSpacing.md,
          vertical: MacrovaSpacing.sm + 2,
        ),
        border: OutlineInputBorder(
          borderRadius: MacrovaRadius.borderSm,
          borderSide: BorderSide(color: tokens.lineStrong),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: MacrovaRadius.borderSm,
          borderSide: BorderSide(color: tokens.lineStrong),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: MacrovaRadius.borderSm,
          borderSide: BorderSide(color: tokens.inkPrimary, width: 1),
        ),
        labelStyle: MacrovaTypography.caption(tokens.inkTertiary),
        hintStyle: MacrovaTypography.body(tokens.inkQuaternary),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: tokens.accent,
          foregroundColor: Colors.white,
          elevation: 0,
          padding: const EdgeInsets.symmetric(
            horizontal: MacrovaSpacing.xl,
            vertical: MacrovaSpacing.md,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: MacrovaRadius.borderSm,
          ),
          textStyle: MacrovaTypography.label(Colors.white),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: tokens.inkPrimary,
          side: BorderSide(color: tokens.lineDefault),
          padding: const EdgeInsets.symmetric(
            horizontal: MacrovaSpacing.xl,
            vertical: MacrovaSpacing.md,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: MacrovaRadius.borderSm,
          ),
          textStyle: MacrovaTypography.label(tokens.inkPrimary),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: tokens.accent,
          textStyle: MacrovaTypography.label(tokens.accent),
        ),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: tokens.surfaceSoft,
        selectedColor: tokens.inkPrimary,
        disabledColor: tokens.surfaceTint,
        labelStyle: MacrovaTypography.bodyMedium(tokens.inkSecondary),
        secondaryLabelStyle: MacrovaTypography.bodyMedium(Colors.white),
        padding: const EdgeInsets.symmetric(
          horizontal: MacrovaSpacing.md,
          vertical: MacrovaSpacing.xs,
        ),
        shape: RoundedRectangleBorder(
          borderRadius: MacrovaRadius.borderPill,
          side: BorderSide(color: tokens.lineDefault),
        ),
        side: BorderSide(color: tokens.lineDefault),
      ),
      segmentedButtonTheme: SegmentedButtonThemeData(
        style: ButtonStyle(
          backgroundColor: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.selected)) {
              return tokens.isDark
                  ? MacrovaColorsDark.surfaceCard
                  : MacrovaColors.backgroundPrimary;
            }
            return Colors.transparent;
          }),
          foregroundColor: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.selected)) {
              return tokens.inkPrimary;
            }
            return tokens.inkTertiary;
          }),
          side: WidgetStateProperty.all(BorderSide(color: tokens.lineDefault)),
          shape: WidgetStateProperty.all(
            RoundedRectangleBorder(borderRadius: MacrovaRadius.borderPill),
          ),
          elevation: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.selected)) return 1;
            return 0;
          }),
        ),
      ),
      navigationRailTheme: NavigationRailThemeData(
        backgroundColor: tokens.isDark
            ? MacrovaColorsDark.backgroundPrimary
            : MacrovaColors.backgroundPrimary,
        selectedIconTheme: IconThemeData(color: tokens.accent),
        unselectedIconTheme: IconThemeData(color: tokens.inkTertiary),
        selectedLabelTextStyle: MacrovaTypography.caption(tokens.accent),
        unselectedLabelTextStyle:
            MacrovaTypography.caption(tokens.inkTertiary),
        indicatorColor: tokens.accentSoft,
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: Colors.transparent,
        indicatorColor: tokens.accentSoft,
        elevation: 0,
        height: 72,
        labelBehavior: NavigationDestinationLabelBehavior.onlyShowSelected,
        iconTheme: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return IconThemeData(color: tokens.accent);
          }
          return IconThemeData(color: tokens.inkTertiary);
        }),
        labelTextStyle: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return MacrovaTypography.caption(tokens.accent);
          }
          return MacrovaTypography.caption(tokens.inkTertiary);
        }),
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: tokens.isDark
            ? MacrovaColorsDark.surfaceSoft
            : tokens.inkPrimary,
        contentTextStyle: MacrovaTypography.body(
          tokens.isDark ? MacrovaColorsDark.inkPrimary : Colors.white,
        ),
        shape: RoundedRectangleBorder(
          borderRadius: MacrovaRadius.borderSm,
        ),
        behavior: SnackBarBehavior.floating,
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: tokens.isDark
            ? MacrovaColorsDark.surfaceCard
            : MacrovaColors.surfaceCard,
        shape: RoundedRectangleBorder(
          borderRadius: MacrovaRadius.borderLg,
          side: BorderSide(color: tokens.lineDefault),
        ),
        titleTextStyle: MacrovaTypography.titleSm(tokens.inkPrimary),
        contentTextStyle: MacrovaTypography.body(tokens.inkSecondary),
      ),
      listTileTheme: ListTileThemeData(
        iconColor: tokens.inkTertiary,
        textColor: tokens.inkPrimary,
        titleTextStyle: MacrovaTypography.label(tokens.inkPrimary),
        subtitleTextStyle: MacrovaTypography.caption(tokens.inkTertiary),
      ),
    );
  }

  static ColorScheme _colorScheme(MacrovaTokens tokens) {
    final surface = tokens.isDark
        ? MacrovaColorsDark.surfaceCard
        : MacrovaColors.surfaceCard;
    final onSurface = tokens.inkPrimary;

    return ColorScheme(
      brightness: tokens.isDark ? Brightness.dark : Brightness.light,
      primary: tokens.accent,
      onPrimary: Colors.white,
      primaryContainer: tokens.accentSoft,
      onPrimaryContainer: tokens.accentDeep,
      secondary: tokens.macroProtein,
      onSecondary: Colors.white,
      secondaryContainer: tokens.surfaceTint,
      onSecondaryContainer: tokens.inkSecondary,
      tertiary: tokens.pinned,
      onTertiary: Colors.white,
      tertiaryContainer: tokens.pinnedSoft,
      onTertiaryContainer: tokens.pinned,
      error: tokens.accent,
      onError: Colors.white,
      errorContainer: tokens.accentSoft,
      onErrorContainer: tokens.accentDeep,
      surface: surface,
      onSurface: onSurface,
      onSurfaceVariant: tokens.inkTertiary,
      outline: tokens.lineDefault,
      outlineVariant: tokens.lineSoft,
      shadow: Colors.black,
      scrim: MacrovaColors.scrim,
      inverseSurface: tokens.inkPrimary,
      onInverseSurface: tokens.isDark
          ? MacrovaColorsDark.inkPrimary
          : MacrovaColors.backgroundPrimary,
      inversePrimary: tokens.accent,
      surfaceTint: tokens.accent,
    );
  }

  static TextTheme _textTheme(MacrovaTokens tokens) {
    return TextTheme(
      displayLarge: MacrovaTypography.display(tokens.inkPrimary),
      displayMedium: MacrovaTypography.headline(tokens.inkPrimary),
      displaySmall: MacrovaTypography.title(tokens.inkPrimary),
      headlineLarge: MacrovaTypography.title(tokens.inkPrimary),
      headlineMedium: MacrovaTypography.titleSm(tokens.inkPrimary),
      headlineSmall: MacrovaTypography.subtitle(tokens.inkPrimary),
      titleLarge: MacrovaTypography.titleSm(tokens.inkPrimary),
      titleMedium: MacrovaTypography.subtitle(tokens.inkPrimary),
      titleSmall: MacrovaTypography.label(tokens.inkPrimary),
      bodyLarge: MacrovaTypography.body(tokens.inkSecondary),
      bodyMedium: MacrovaTypography.bodyMedium(tokens.inkSecondary),
      bodySmall: MacrovaTypography.caption(tokens.inkTertiary),
      labelLarge: MacrovaTypography.label(tokens.inkPrimary),
      labelMedium: MacrovaTypography.labelCaps(tokens.inkTertiary),
      labelSmall: MacrovaTypography.caption(tokens.inkQuaternary),
    );
  }
}
