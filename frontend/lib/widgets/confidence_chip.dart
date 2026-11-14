import 'package:flutter/material.dart';

import '../theme/tokens.dart';

enum ConfidenceLevel { hi, mid, none }

class ConfidenceChip extends StatelessWidget {
  final ConfidenceLevel level;
  final String? label;

  const ConfidenceChip({
    super.key,
    required this.level,
    this.label,
  });

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;
    final colors = _colors(tokens);
    final text = label ?? _defaultLabel();

    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: MacrovaSpacing.sm,
        vertical: MacrovaSpacing.xs,
      ),
      decoration: BoxDecoration(
        color: colors.background,
        borderRadius: MacrovaRadius.borderPill,
        border: Border.all(color: colors.border),
      ),
      child: Text(
        text,
        style: MacrovaTypography.caption(colors.foreground).copyWith(
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }

  String _defaultLabel() {
    return switch (level) {
      ConfidenceLevel.hi => 'High match',
      ConfidenceLevel.mid => 'Partial match',
      ConfidenceLevel.none => 'No match',
    };
  }

  _ConfidenceColors _colors(MacrovaTokens tokens) {
    return switch (level) {
      ConfidenceLevel.hi => _ConfidenceColors(
          background: tokens.semanticSuccessBg,
          foreground: tokens.semanticSuccessText,
          border: tokens.semanticSuccess.withValues(alpha: 0.3),
        ),
      ConfidenceLevel.mid => _ConfidenceColors(
          background: tokens.semanticWarningBg,
          foreground: tokens.semanticWarningText,
          border: tokens.semanticWarning.withValues(alpha: 0.3),
        ),
      ConfidenceLevel.none => _ConfidenceColors(
          background: tokens.accentSoft,
          foreground: tokens.accentDeep,
          border: tokens.accentTint,
        ),
    };
  }
}

class _ConfidenceColors {
  final Color background;
  final Color foreground;
  final Color border;

  const _ConfidenceColors({
    required this.background,
    required this.foreground,
    required this.border,
  });
}
