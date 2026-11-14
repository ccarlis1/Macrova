import 'package:flutter/material.dart';

import '../theme/tokens.dart';

enum StatCardVariant { protein, carb, fat }

class StatCard extends StatelessWidget {
  final String label;
  final String value;
  final String? unit;
  final double? progress;
  final StatCardVariant? variant;

  const StatCard({
    super.key,
    required this.label,
    required this.value,
    this.unit,
    this.progress,
    this.variant,
  });

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;
    final tintColor = _tintColor(tokens);
    final barColor = _barColor(tokens);

    return Container(
      padding: const EdgeInsets.all(MacrovaSpacing.lg),
      decoration: BoxDecoration(
        color: tintColor.withValues(alpha: 0.12),
        borderRadius: MacrovaRadius.borderMd,
        border: Border.all(color: tokens.lineDefault),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            MacrovaTypography.labelCapsText(label),
            style: MacrovaTypography.labelCaps(tokens.inkTertiary),
          ),
          const SizedBox(height: MacrovaSpacing.sm),
          Row(
            crossAxisAlignment: CrossAxisAlignment.baseline,
            textBaseline: TextBaseline.alphabetic,
            children: [
              Text(
                value,
                style: MacrovaTypography.metric(tokens.inkPrimary),
              ),
              if (unit != null) ...[
                const SizedBox(width: MacrovaSpacing.xs),
                Text(
                  unit!,
                  style: MacrovaTypography.metricUnit(tokens.inkTertiary),
                ),
              ],
            ],
          ),
          if (progress != null) ...[
            const SizedBox(height: MacrovaSpacing.md),
            ClipRRect(
              borderRadius: BorderRadius.circular(2),
              child: LinearProgressIndicator(
                value: progress!.clamp(0.0, 1.0),
                minHeight: 4,
                backgroundColor: barColor.withValues(alpha: 0.15),
                color: barColor,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Color _tintColor(MacrovaTokens tokens) {
    return switch (variant) {
      StatCardVariant.protein => tokens.macroProtein,
      StatCardVariant.carb => tokens.macroCarb,
      StatCardVariant.fat => tokens.macroFat,
      null => tokens.surfaceTint,
    };
  }

  Color _barColor(MacrovaTokens tokens) {
    if (progress != null && progress! > 1.0) return tokens.macroFat;
    return _tintColor(tokens);
  }
}
