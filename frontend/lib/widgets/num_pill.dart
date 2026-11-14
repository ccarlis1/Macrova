import 'package:flutter/material.dart';

import '../theme/tokens.dart';

class NumPill extends StatelessWidget {
  final num value;
  final ValueChanged<num> onChange;
  final num? min;
  final num step;
  final String? unit;
  final List<String>? units;
  final ValueChanged<String>? onUnitChanged;

  const NumPill({
    super.key,
    required this.value,
    required this.onChange,
    this.min,
    this.step = 1,
    this.unit,
    this.units,
    this.onUnitChanged,
  });

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;
    final floor = min ?? 0;
    final canDecrement = value - step >= floor;

    return Container(
      decoration: BoxDecoration(
        border: Border.all(color: tokens.lineStrong),
        borderRadius: MacrovaRadius.borderPill,
        color: tokens.isDark
            ? MacrovaColorsDark.surfaceCard
            : MacrovaColors.backgroundPrimary,
      ),
      clipBehavior: Clip.antiAlias,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _StepButton(
            icon: Icons.remove,
            onPressed: canDecrement ? () => onChange(value - step) : null,
            tokens: tokens,
          ),
          SizedBox(
            width: units != null ? 56 : 44,
            child: Text(
              _formatValue(value),
              textAlign: TextAlign.center,
              style: MacrovaTypography.subtitle(tokens.inkPrimary).copyWith(
                fontFeatures: MacrovaTypography.tabularFigures,
              ),
            ),
          ),
          _StepButton(
            icon: Icons.add,
            onPressed: () => onChange(value + step),
            tokens: tokens,
          ),
          if (unit != null || (units != null && units!.isNotEmpty)) ...[
            Container(
              width: 1,
              height: 38,
              color: tokens.lineDefault,
            ),
            _UnitSelector(
              unit: unit,
              units: units,
              onUnitChanged: onUnitChanged,
              tokens: tokens,
            ),
          ],
        ],
      ),
    );
  }

  String _formatValue(num v) {
    if (v is int || v == v.roundToDouble()) return v.round().toString();
    return v.toStringAsFixed(1);
  }
}

class _StepButton extends StatelessWidget {
  final IconData icon;
  final VoidCallback? onPressed;
  final MacrovaTokens tokens;

  const _StepButton({
    required this.icon,
    required this.onPressed,
    required this.tokens,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 38,
      height: 38,
      child: IconButton(
        onPressed: onPressed,
        icon: Icon(icon, size: 20),
        color: onPressed != null ? tokens.inkSecondary : tokens.inkQuaternary,
        padding: EdgeInsets.zero,
        constraints: const BoxConstraints(),
      ),
    );
  }
}

class _UnitSelector extends StatelessWidget {
  final String? unit;
  final List<String>? units;
  final ValueChanged<String>? onUnitChanged;
  final MacrovaTokens tokens;

  const _UnitSelector({
    required this.unit,
    required this.units,
    required this.onUnitChanged,
    required this.tokens,
  });

  @override
  Widget build(BuildContext context) {
    if (units != null && units!.length > 1 && onUnitChanged != null) {
      return DropdownButtonHideUnderline(
        child: DropdownButton<String>(
          value: unit ?? units!.first,
          items: units!
              .map(
                (u) => DropdownMenuItem(
                  value: u,
                  child: Text(
                    u,
                    style: MacrovaTypography.bodyMedium(tokens.inkSecondary),
                  ),
                ),
              )
              .toList(),
          onChanged: (v) {
            if (v != null) onUnitChanged!(v);
          },
          padding: const EdgeInsets.symmetric(horizontal: MacrovaSpacing.sm),
        ),
      );
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: MacrovaSpacing.md),
      child: Text(
        unit ?? units?.first ?? '',
        style: MacrovaTypography.bodyMedium(tokens.inkSecondary),
      ),
    );
  }
}
