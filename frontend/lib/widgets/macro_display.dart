import 'package:flutter/material.dart';

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
    final style = compact
        ? Theme.of(context).textTheme.bodySmall
        : Theme.of(context).textTheme.bodyMedium;

    return Wrap(
      spacing: compact ? 8 : 16,
      runSpacing: 4,
      children: [
        _chip('Cal', '${calories.round()}', Colors.orange, style),
        _chip('P', '${proteinG.round()}g', Colors.red, style),
        _chip('C', '${carbsG.round()}g', Colors.amber.shade700, style),
        _chip('F', '${fatG.round()}g', Colors.blue, style),
      ],
    );
  }

  Widget _chip(String label, String value, Color color, TextStyle? style) {
    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: compact ? 6 : 8,
        vertical: compact ? 2 : 4,
      ),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        '$label $value',
        style: style?.copyWith(
          color: color,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}
