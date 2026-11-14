import 'package:flutter/material.dart';

import '../theme/tokens.dart';

enum SegmentedControlStyle { pill, busyness }

class SegmentedControl<T extends Object> extends StatelessWidget {
  final List<SegmentedOption<T>> options;
  final T value;
  final ValueChanged<T> onChanged;
  final SegmentedControlStyle style;

  const SegmentedControl({
    super.key,
    required this.options,
    required this.value,
    required this.onChanged,
    this.style = SegmentedControlStyle.pill,
  });

  @override
  Widget build(BuildContext context) {
    if (style == SegmentedControlStyle.busyness) {
      return _BusynessSegmented(
        options: options,
        value: value,
        onChanged: onChanged,
      );
    }

    final tokens = Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;

    return SegmentedButton<T>(
      style: _pillStyle(tokens),
      segments: options
          .map(
            (o) => ButtonSegment<T>(
              value: o.value,
              label: Text(o.label),
              icon: o.icon != null ? Icon(o.icon, size: 16) : null,
            ),
          )
          .toList(),
      selected: {value},
      onSelectionChanged: (selected) {
        if (selected.isNotEmpty) onChanged(selected.first);
      },
      showSelectedIcon: false,
    );
  }

  static ButtonStyle _pillStyle(MacrovaTokens tokens) {
    return ButtonStyle(
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
      textStyle: WidgetStateProperty.all(
        MacrovaTypography.label(tokens.inkTertiary).copyWith(
          fontFeatures: MacrovaTypography.tabularFigures,
        ),
      ),
    );
  }
}

class SegmentedOption<T> {
  final T value;
  final String label;
  final IconData? icon;

  const SegmentedOption({
    required this.value,
    required this.label,
    this.icon,
  });
}

class _BusynessSegmented<T extends Object> extends StatelessWidget {
  final List<SegmentedOption<T>> options;
  final T value;
  final ValueChanged<T> onChanged;

  const _BusynessSegmented({
    required this.options,
    required this.value,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;

    return Container(
      decoration: BoxDecoration(
        border: Border.all(color: tokens.lineDefault),
        borderRadius: MacrovaRadius.borderSm,
        color: tokens.surfaceTint,
      ),
      clipBehavior: Clip.antiAlias,
      child: Row(
        children: [
          for (var i = 0; i < options.length; i++)
            Expanded(
              child: _BusynessButton<T>(
                option: options[i],
                isSelected: options[i].value == value,
                showDivider: i < options.length - 1,
                onTap: () => onChanged(options[i].value),
                tokens: tokens,
              ),
            ),
        ],
      ),
    );
  }
}

class _BusynessButton<T> extends StatelessWidget {
  final SegmentedOption<T> option;
  final bool isSelected;
  final bool showDivider;
  final VoidCallback onTap;
  final MacrovaTokens tokens;

  const _BusynessButton({
    required this.option,
    required this.isSelected,
    required this.showDivider,
    required this.onTap,
    required this.tokens,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: isSelected ? tokens.inkPrimary : Colors.transparent,
      child: InkWell(
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: MacrovaSpacing.sm),
          decoration: BoxDecoration(
            border: showDivider
                ? Border(
                    right: BorderSide(color: tokens.lineDefault),
                  )
                : null,
          ),
          alignment: Alignment.center,
          child: Text(
            option.label,
            style: MacrovaTypography.label(
              isSelected ? MacrovaColors.onDarkFill : tokens.inkTertiary,
            ).copyWith(fontFeatures: MacrovaTypography.tabularFigures),
          ),
        ),
      ),
    );
  }
}
