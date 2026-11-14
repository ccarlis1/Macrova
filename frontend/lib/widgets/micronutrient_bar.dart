import 'package:flutter/material.dart';

import '../theme/tokens.dart';

/// Micro-nutrient progress row or stacked macro-split bar.
class MicronutrientBar extends StatelessWidget {
  final String? label;
  final double? value;
  final double? target;
  final String? unit;
  final bool isLimit;

  final double? proteinG;
  final double? carbsG;
  final double? fatG;
  final bool showLegend;

  const MicronutrientBar({
    super.key,
    required this.label,
    required this.value,
    required this.target,
    required this.unit,
    this.isLimit = false,
  })  : proteinG = null,
        carbsG = null,
        fatG = null,
        showLegend = true;

  const MicronutrientBar.macroSplit({
    super.key,
    required this.proteinG,
    required this.carbsG,
    required this.fatG,
    this.showLegend = true,
  })  : label = null,
        value = null,
        target = null,
        unit = null,
        isLimit = false;

  @override
  Widget build(BuildContext context) {
    if (proteinG != null && carbsG != null && fatG != null) {
      return _MacroSplitBar(
        proteinG: proteinG!,
        carbsG: carbsG!,
        fatG: fatG!,
        showLegend: showLegend,
      );
    }
    return _MicroRow(
      label: label!,
      value: value!,
      target: target!,
      unit: unit!,
      isLimit: isLimit,
    );
  }
}

class _MicroRow extends StatelessWidget {
  final String label;
  final double value;
  final double target;
  final String unit;
  final bool isLimit;

  const _MicroRow({
    required this.label,
    required this.value,
    required this.target,
    required this.unit,
    required this.isLimit,
  });

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;
    final pct = target > 0 ? (value / target).clamp(0.0, 1.5) : 0.0;
    final displayPct = (pct * 100).round();
    final barColor = _barColor(tokens, pct, isLimit);

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: MacrovaSpacing.xs),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Text(
                  label,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ),
              Text(
                '${value.toStringAsFixed(value < 10 ? 1 : 0)} $unit/ '
                '${target.toStringAsFixed(target < 10 ? 1 : 0)} $unit',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      fontFeatures: MacrovaTypography.tabularFigures,
                    ),
              ),
            ],
          ),
          const SizedBox(height: 2),
          Row(
            children: [
              Expanded(
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(2),
                  child: LinearProgressIndicator(
                    value: pct.clamp(0.0, 1.0).toDouble(),
                    backgroundColor: barColor.withValues(alpha: 0.15),
                    color: barColor,
                    minHeight: 6,
                  ),
                ),
              ),
              const SizedBox(width: MacrovaSpacing.sm),
              SizedBox(
                width: 55,
                child: Text(
                  '$displayPct% ${isLimit ? "limit" : "RDA"}',
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: barColor,
                        fontWeight: FontWeight.w600,
                        fontFeatures: MacrovaTypography.tabularFigures,
                      ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Color _barColor(MacrovaTokens tokens, double pct, bool isLimit) {
    if (isLimit) {
      return pct > 1.0 ? tokens.accent : tokens.semanticSuccess;
    }
    if (pct >= 0.8) return tokens.semanticSuccess;
    if (pct >= 0.5) return tokens.semanticWarning;
    return tokens.accent;
  }
}

class _MacroSplitBar extends StatelessWidget {
  final double proteinG;
  final double carbsG;
  final double fatG;
  final bool showLegend;

  const _MacroSplitBar({
    required this.proteinG,
    required this.carbsG,
    required this.fatG,
    required this.showLegend,
  });

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;
    final proteinKcal = proteinG * 4;
    final carbsKcal = carbsG * 4;
    final fatKcal = fatG * 9;
    final total = proteinKcal + carbsKcal + fatKcal;
    final proteinPct = total > 0 ? (proteinKcal / total * 100).round() : 0;
    final carbsPct = total > 0 ? (carbsKcal / total * 100).round() : 0;
    final fatPct = total > 0 ? 100 - proteinPct - carbsPct : 0;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(2),
          child: SizedBox(
            height: 7,
            child: total <= 0
                ? Container(color: tokens.lineSoft)
                : Row(
                    children: [
                      if (proteinPct > 0)
                        Expanded(
                          flex: proteinPct,
                          child: ColoredBox(color: tokens.macroProtein),
                        ),
                      if (carbsPct > 0)
                        Expanded(
                          flex: carbsPct,
                          child: ColoredBox(color: tokens.macroCarb),
                        ),
                      if (fatPct > 0)
                        Expanded(
                          flex: fatPct,
                          child: ColoredBox(color: tokens.macroFat),
                        ),
                    ],
                  ),
          ),
        ),
        if (showLegend) ...[
          const SizedBox(height: MacrovaSpacing.sm),
          Wrap(
            spacing: MacrovaSpacing.lg,
            runSpacing: MacrovaSpacing.xs,
            children: [
              _legendItem(tokens.macroProtein, 'Protein $proteinPct%'),
              _legendItem(tokens.macroCarb, 'Carbs $carbsPct%'),
              _legendItem(tokens.macroFat, 'Fat $fatPct%'),
            ],
          ),
        ],
      ],
    );
  }

  Widget _legendItem(Color color, String text) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 8,
          height: 8,
          decoration: BoxDecoration(
            color: color,
            shape: BoxShape.circle,
          ),
        ),
        const SizedBox(width: MacrovaSpacing.xs + 2),
        Text(
          text,
          style: MacrovaTypography.caption(color).copyWith(
            color: color,
            fontFeatures: MacrovaTypography.tabularFigures,
          ),
        ),
      ],
    );
  }
}
