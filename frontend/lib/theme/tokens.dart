import 'package:flutter/material.dart';

/// Raw design tokens from [visual-language-extraction.md].
/// Dark values are an assumption — prototype is light-only.
abstract final class MacrovaColors {
  // Backgrounds & surfaces (light)
  static const Color canvas = Color(0xFFF7F7F7);
  static const Color backgroundPrimary = Color(0xFFFFFFFF);
  static const Color surfaceCard = Color(0xFFFFFFFF);
  static const Color surfaceTint = Color(0xFFFAFAFA);
  static const Color surfaceSoft = Color(0xFFF7F7F7);

  // Lines (light)
  static const Color lineDefault = Color(0xFFEBEBEB);
  static const Color lineSoft = Color(0xFFF0F0F0);
  static const Color lineStrong = Color(0xFFDDDDDD);

  // Ink (light)
  static const Color inkPrimary = Color(0xFF222222);
  static const Color inkSecondary = Color(0xFF555555);
  static const Color inkTertiary = Color(0xFF767676);
  static const Color inkQuaternary = Color(0xFFB0B0B0);

  // Accent (shared)
  static const Color accent = Color(0xFFC44A4A);
  static const Color accentDeep = Color(0xFFA43A3A);
  static const Color accentSoft = Color(0xFFFDF3F0);
  static const Color accentTint = Color(0xFFFAEEEA);

  // Pinned (shared)
  static const Color pinned = Color(0xFF4A3A2E);
  static const Color pinnedSoft = Color(0xFFF5EFE7);

  // Macro (shared)
  static const Color macroProtein = Color(0xFF5A7A8A);
  static const Color macroCarb = Color(0xFFC69A4A);
  static const Color macroFat = Color(0xFFB56B5A);

  // Semantic (light)
  static const Color semanticSuccess = Color(0xFF5FA874);
  static const Color semanticSuccessText = Color(0xFF2F7D4F);
  static const Color semanticSuccessBg = Color(0xFFE8F3EC);
  static const Color semanticWarning = Color(0xFFD4A850);
  static const Color semanticWarningText = Color(0xFF9A6A1A);
  static const Color semanticWarningBg = Color(0xFFFBF2E2);
  static const Color semanticMock = Color(0xFFA8A4B8);

  // Translucency
  static const Color scrim = Color(0x66000000);
  static const Color stickyBarLight = Color(0xF0FFFFFF);
}

/// Dark-mode surface and ink tokens (assumption).
abstract final class MacrovaColorsDark {
  static const Color canvas = Color(0xFF121212);
  static const Color backgroundPrimary = Color(0xFF1A1A1A);
  static const Color surfaceCard = Color(0xFF1E1E1E);
  static const Color surfaceTint = Color(0xFF252525);
  static const Color surfaceSoft = Color(0xFF2A2A2A);

  static const Color lineDefault = Color(0xFF333333);
  static const Color lineSoft = Color(0xFF2C2C2C);
  static const Color lineStrong = Color(0xFF444444);

  static const Color inkPrimary = Color(0xFFF0F0F0);
  static const Color inkSecondary = Color(0xFFB8B8B8);
  static const Color inkTertiary = Color(0xFF8A8A8A);
  static const Color inkQuaternary = Color(0xFF5A5A5A);

  static const Color accentSoft = Color(0xFF3D2A28);
  static const Color accentTint = Color(0xFF4A3230);
  static const Color pinnedSoft = Color(0xFF3A3428);

  static const Color semanticSuccessBg = Color(0xFF1E3328);
  static const Color semanticWarningBg = Color(0xFF3A3020);
  static const Color stickyBarDark = Color(0xF01A1A1A);
}

abstract final class MacrovaSpacing {
  static const double xs = 4;
  static const double sm = 8;
  static const double md = 12;
  static const double lg = 16;
  static const double lgAlt = 18;
  static const double xl = 20;
  static const double xlAlt = 24;
  static const double xxl = 32;

  /// Screen horizontal gutter.
  static const double screenGutter = 20;

  /// Section top spacing.
  static const double sectionTop = 24;

  /// Sheet body bottom padding to clear sticky CTA.
  static const double sheetBottomClearance = 120;

  /// Mobile column max width.
  static const double mobileMaxWidth = 480;
}

abstract final class MacrovaRadius {
  static const double sm = 8;
  static const double md = 12;
  static const double lg = 16;
  static const double xl = 24;
  static const double pill = 999;
  static const double frame = 28;

  static BorderRadius get borderSm => BorderRadius.circular(sm);
  static BorderRadius get borderMd => BorderRadius.circular(md);
  static BorderRadius get borderLg => BorderRadius.circular(lg);
  static BorderRadius get borderPill => BorderRadius.circular(pill);
}

abstract final class MacrovaElevation {
  static const List<BoxShadow> none = [];

  static const List<BoxShadow> shadow1 = [
    BoxShadow(
      color: Color(0x0A000000),
      blurRadius: 2,
      offset: Offset(0, 1),
    ),
  ];

  static const List<BoxShadow> shadow2 = [
    BoxShadow(
      color: Color(0x0F000000),
      blurRadius: 8,
      offset: Offset(0, 2),
    ),
  ];

  static const List<BoxShadow> shadow3 = [
    BoxShadow(
      color: Color(0x14000000),
      blurRadius: 20,
      offset: Offset(0, 6),
    ),
  ];

  static const List<BoxShadow> shadowCta = [
    BoxShadow(
      color: Color(0x0A000000),
      blurRadius: 16,
      offset: Offset(0, -4),
    ),
  ];
}

/// Typography roles with tabular figures on metrics.
abstract final class MacrovaTypography {
  static const List<FontFeature> tabularFigures = [
    FontFeature.tabularFigures(),
  ];

  static TextStyle display(Color color) => TextStyle(
        fontSize: 28,
        fontWeight: FontWeight.w600,
        letterSpacing: -0.62,
        color: color,
        height: 1.2,
      );

  static TextStyle headline(Color color) => TextStyle(
        fontSize: 24,
        fontWeight: FontWeight.w600,
        letterSpacing: -0.43,
        color: color,
        height: 1.25,
      );

  static TextStyle title(Color color) => TextStyle(
        fontSize: 22,
        fontWeight: FontWeight.w600,
        letterSpacing: -0.4,
        color: color,
        height: 1.3,
      );

  static TextStyle titleSm(Color color) => TextStyle(
        fontSize: 17,
        fontWeight: FontWeight.w600,
        letterSpacing: -0.17,
        color: color,
        height: 1.35,
      );

  static TextStyle subtitle(Color color) => TextStyle(
        fontSize: 16,
        fontWeight: FontWeight.w600,
        letterSpacing: -0.16,
        color: color,
        height: 1.4,
      );

  static TextStyle body(Color color) => TextStyle(
        fontSize: 15,
        fontWeight: FontWeight.w400,
        color: color,
        height: 1.45,
      );

  static TextStyle bodyMedium(Color color) => TextStyle(
        fontSize: 14,
        fontWeight: FontWeight.w500,
        color: color,
        height: 1.5,
      );

  static TextStyle label(Color color) => TextStyle(
        fontSize: 14,
        fontWeight: FontWeight.w600,
        letterSpacing: -0.07,
        color: color,
        height: 1.4,
      );

  /// Uppercase micro-label style (11px, 0.06em tracking).
  ///
  /// Flutter [TextStyle] has no CSS-style text-transform; use [labelCapsText]
  /// on the string when rendering.
  static String labelCapsText(String value) => value.toUpperCase();

  static TextStyle labelCaps(Color color) => TextStyle(
        fontSize: 11,
        fontWeight: FontWeight.w600,
        letterSpacing: 0.66,
        color: color,
        height: 1.3,
      );

  static TextStyle caption(Color color) => TextStyle(
        fontSize: 12,
        fontWeight: FontWeight.w400,
        color: color,
        height: 1.4,
      );

  static TextStyle metric(Color color) => TextStyle(
        fontSize: 24,
        fontWeight: FontWeight.w600,
        letterSpacing: -0.24,
        color: color,
        height: 1.2,
        fontFeatures: tabularFigures,
      );

  static TextStyle metricUnit(Color color) => TextStyle(
        fontSize: 12,
        fontWeight: FontWeight.w400,
        color: color,
        height: 1.3,
        fontFeatures: tabularFigures,
      );

  static TextStyle mono(Color color) => TextStyle(
        fontSize: 11,
        fontWeight: FontWeight.w400,
        color: color,
        height: 1.4,
        fontFamily: 'monospace',
        fontFeatures: tabularFigures,
      );
}

/// Non-Material tokens exposed via [ThemeExtension].
@immutable
class MacrovaTokens extends ThemeExtension<MacrovaTokens> {
  const MacrovaTokens({
    required this.canvas,
    required this.surfaceTint,
    required this.surfaceSoft,
    required this.lineDefault,
    required this.lineSoft,
    required this.lineStrong,
    required this.inkPrimary,
    required this.inkSecondary,
    required this.inkTertiary,
    required this.inkQuaternary,
    required this.accent,
    required this.accentDeep,
    required this.accentSoft,
    required this.accentTint,
    required this.pinned,
    required this.pinnedSoft,
    required this.macroProtein,
    required this.macroCarb,
    required this.macroFat,
    required this.semanticSuccess,
    required this.semanticSuccessText,
    required this.semanticSuccessBg,
    required this.semanticWarning,
    required this.semanticWarningText,
    required this.semanticWarningBg,
    required this.semanticMock,
    required this.stickyBar,
    required this.isDark,
  });

  final Color canvas;
  final Color surfaceTint;
  final Color surfaceSoft;
  final Color lineDefault;
  final Color lineSoft;
  final Color lineStrong;
  final Color inkPrimary;
  final Color inkSecondary;
  final Color inkTertiary;
  final Color inkQuaternary;
  final Color accent;
  final Color accentDeep;
  final Color accentSoft;
  final Color accentTint;
  final Color pinned;
  final Color pinnedSoft;
  final Color macroProtein;
  final Color macroCarb;
  final Color macroFat;
  final Color semanticSuccess;
  final Color semanticSuccessText;
  final Color semanticSuccessBg;
  final Color semanticWarning;
  final Color semanticWarningText;
  final Color semanticWarningBg;
  final Color semanticMock;
  final Color stickyBar;
  final bool isDark;

  static const MacrovaTokens light = MacrovaTokens(
    canvas: MacrovaColors.canvas,
    surfaceTint: MacrovaColors.surfaceTint,
    surfaceSoft: MacrovaColors.surfaceSoft,
    lineDefault: MacrovaColors.lineDefault,
    lineSoft: MacrovaColors.lineSoft,
    lineStrong: MacrovaColors.lineStrong,
    inkPrimary: MacrovaColors.inkPrimary,
    inkSecondary: MacrovaColors.inkSecondary,
    inkTertiary: MacrovaColors.inkTertiary,
    inkQuaternary: MacrovaColors.inkQuaternary,
    accent: MacrovaColors.accent,
    accentDeep: MacrovaColors.accentDeep,
    accentSoft: MacrovaColors.accentSoft,
    accentTint: MacrovaColors.accentTint,
    pinned: MacrovaColors.pinned,
    pinnedSoft: MacrovaColors.pinnedSoft,
    macroProtein: MacrovaColors.macroProtein,
    macroCarb: MacrovaColors.macroCarb,
    macroFat: MacrovaColors.macroFat,
    semanticSuccess: MacrovaColors.semanticSuccess,
    semanticSuccessText: MacrovaColors.semanticSuccessText,
    semanticSuccessBg: MacrovaColors.semanticSuccessBg,
    semanticWarning: MacrovaColors.semanticWarning,
    semanticWarningText: MacrovaColors.semanticWarningText,
    semanticWarningBg: MacrovaColors.semanticWarningBg,
    semanticMock: MacrovaColors.semanticMock,
    stickyBar: MacrovaColors.stickyBarLight,
    isDark: false,
  );

  static const MacrovaTokens dark = MacrovaTokens(
    canvas: MacrovaColorsDark.canvas,
    surfaceTint: MacrovaColorsDark.surfaceTint,
    surfaceSoft: MacrovaColorsDark.surfaceSoft,
    lineDefault: MacrovaColorsDark.lineDefault,
    lineSoft: MacrovaColorsDark.lineSoft,
    lineStrong: MacrovaColorsDark.lineStrong,
    inkPrimary: MacrovaColorsDark.inkPrimary,
    inkSecondary: MacrovaColorsDark.inkSecondary,
    inkTertiary: MacrovaColorsDark.inkTertiary,
    inkQuaternary: MacrovaColorsDark.inkQuaternary,
    accent: MacrovaColors.accent,
    accentDeep: MacrovaColors.accentDeep,
    accentSoft: MacrovaColorsDark.accentSoft,
    accentTint: MacrovaColorsDark.accentTint,
    pinned: MacrovaColors.pinned,
    pinnedSoft: MacrovaColorsDark.pinnedSoft,
    macroProtein: MacrovaColors.macroProtein,
    macroCarb: MacrovaColors.macroCarb,
    macroFat: MacrovaColors.macroFat,
    semanticSuccess: MacrovaColors.semanticSuccess,
    semanticSuccessText: MacrovaColors.semanticSuccessText,
    semanticSuccessBg: MacrovaColorsDark.semanticSuccessBg,
    semanticWarning: MacrovaColors.semanticWarning,
    semanticWarningText: MacrovaColors.semanticWarningText,
    semanticWarningBg: MacrovaColorsDark.semanticWarningBg,
    semanticMock: MacrovaColors.semanticMock,
    stickyBar: MacrovaColorsDark.stickyBarDark,
    isDark: true,
  );

  @override
  MacrovaTokens copyWith({
    Color? canvas,
    Color? surfaceTint,
    Color? surfaceSoft,
    Color? lineDefault,
    Color? lineSoft,
    Color? lineStrong,
    Color? inkPrimary,
    Color? inkSecondary,
    Color? inkTertiary,
    Color? inkQuaternary,
    Color? accent,
    Color? accentDeep,
    Color? accentSoft,
    Color? accentTint,
    Color? pinned,
    Color? pinnedSoft,
    Color? macroProtein,
    Color? macroCarb,
    Color? macroFat,
    Color? semanticSuccess,
    Color? semanticSuccessText,
    Color? semanticSuccessBg,
    Color? semanticWarning,
    Color? semanticWarningText,
    Color? semanticWarningBg,
    Color? semanticMock,
    Color? stickyBar,
    bool? isDark,
  }) {
    return MacrovaTokens(
      canvas: canvas ?? this.canvas,
      surfaceTint: surfaceTint ?? this.surfaceTint,
      surfaceSoft: surfaceSoft ?? this.surfaceSoft,
      lineDefault: lineDefault ?? this.lineDefault,
      lineSoft: lineSoft ?? this.lineSoft,
      lineStrong: lineStrong ?? this.lineStrong,
      inkPrimary: inkPrimary ?? this.inkPrimary,
      inkSecondary: inkSecondary ?? this.inkSecondary,
      inkTertiary: inkTertiary ?? this.inkTertiary,
      inkQuaternary: inkQuaternary ?? this.inkQuaternary,
      accent: accent ?? this.accent,
      accentDeep: accentDeep ?? this.accentDeep,
      accentSoft: accentSoft ?? this.accentSoft,
      accentTint: accentTint ?? this.accentTint,
      pinned: pinned ?? this.pinned,
      pinnedSoft: pinnedSoft ?? this.pinnedSoft,
      macroProtein: macroProtein ?? this.macroProtein,
      macroCarb: macroCarb ?? this.macroCarb,
      macroFat: macroFat ?? this.macroFat,
      semanticSuccess: semanticSuccess ?? this.semanticSuccess,
      semanticSuccessText: semanticSuccessText ?? this.semanticSuccessText,
      semanticSuccessBg: semanticSuccessBg ?? this.semanticSuccessBg,
      semanticWarning: semanticWarning ?? this.semanticWarning,
      semanticWarningText: semanticWarningText ?? this.semanticWarningText,
      semanticWarningBg: semanticWarningBg ?? this.semanticWarningBg,
      semanticMock: semanticMock ?? this.semanticMock,
      stickyBar: stickyBar ?? this.stickyBar,
      isDark: isDark ?? this.isDark,
    );
  }

  @override
  MacrovaTokens lerp(ThemeExtension<MacrovaTokens>? other, double t) {
    if (other is! MacrovaTokens) return this;
    return MacrovaTokens(
      canvas: Color.lerp(canvas, other.canvas, t)!,
      surfaceTint: Color.lerp(surfaceTint, other.surfaceTint, t)!,
      surfaceSoft: Color.lerp(surfaceSoft, other.surfaceSoft, t)!,
      lineDefault: Color.lerp(lineDefault, other.lineDefault, t)!,
      lineSoft: Color.lerp(lineSoft, other.lineSoft, t)!,
      lineStrong: Color.lerp(lineStrong, other.lineStrong, t)!,
      inkPrimary: Color.lerp(inkPrimary, other.inkPrimary, t)!,
      inkSecondary: Color.lerp(inkSecondary, other.inkSecondary, t)!,
      inkTertiary: Color.lerp(inkTertiary, other.inkTertiary, t)!,
      inkQuaternary: Color.lerp(inkQuaternary, other.inkQuaternary, t)!,
      accent: Color.lerp(accent, other.accent, t)!,
      accentDeep: Color.lerp(accentDeep, other.accentDeep, t)!,
      accentSoft: Color.lerp(accentSoft, other.accentSoft, t)!,
      accentTint: Color.lerp(accentTint, other.accentTint, t)!,
      pinned: Color.lerp(pinned, other.pinned, t)!,
      pinnedSoft: Color.lerp(pinnedSoft, other.pinnedSoft, t)!,
      macroProtein: Color.lerp(macroProtein, other.macroProtein, t)!,
      macroCarb: Color.lerp(macroCarb, other.macroCarb, t)!,
      macroFat: Color.lerp(macroFat, other.macroFat, t)!,
      semanticSuccess: Color.lerp(semanticSuccess, other.semanticSuccess, t)!,
      semanticSuccessText:
          Color.lerp(semanticSuccessText, other.semanticSuccessText, t)!,
      semanticSuccessBg:
          Color.lerp(semanticSuccessBg, other.semanticSuccessBg, t)!,
      semanticWarning: Color.lerp(semanticWarning, other.semanticWarning, t)!,
      semanticWarningText:
          Color.lerp(semanticWarningText, other.semanticWarningText, t)!,
      semanticWarningBg:
          Color.lerp(semanticWarningBg, other.semanticWarningBg, t)!,
      semanticMock: Color.lerp(semanticMock, other.semanticMock, t)!,
      stickyBar: Color.lerp(stickyBar, other.stickyBar, t)!,
      isDark: t < 0.5 ? isDark : other.isDark,
    );
  }
}
