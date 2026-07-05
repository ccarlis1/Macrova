import 'package:flutter/material.dart';

import '../theme/tokens.dart';

class MacroDisplay extends StatelessWidget {
  final double calories;
  final double proteinG;
  final double carbsG;
  final double fatG;
  final bool compact;

  const MacroDisplay({
    super.key,
    required this.calories,
    required this.proteinG,
    required this.carbsG,
    required this.fatG,
    this.compact = false,
  });

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;
    final style = compact
        ? Theme.of(context).textTheme.bodySmall
        : Theme.of(context).textTheme.bodyMedium;

    return Wrap(
      spacing: compact ? MacrovaSpacing.sm : MacrovaSpacing.lg,
      runSpacing: MacrovaSpacing.xs,
      children: [
        _chip('Cal', '${calories.round()}', tokens.inkSecondary, style),
        _chip('P', '${proteinG.round()}g', tokens.macroProtein, style),
        _chip('C', '${carbsG.round()}g', tokens.macroCarb, style),
        _chip('F', '${fatG.round()}g', tokens.macroFat, style),
      ],
    );
  }

  Widget _chip(String label, String value, Color color, TextStyle? style) {
    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: compact ? 6 : MacrovaSpacing.sm,
        vertical: compact ? 2 : MacrovaSpacing.xs,
      ),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(MacrovaRadius.sm),
      ),
      child: Text(
        '$label $value',
        style: style?.copyWith(
          color: color,
          fontWeight: FontWeight.w600,
          fontFeatures: MacrovaTypography.tabularFigures,
        ),
      ),
    );
  }
}
