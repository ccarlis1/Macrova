import 'package:flutter/material.dart';

import '../theme/tokens.dart';
import 'dashed_border.dart';

enum MacrovaChipVariant {
  default_,
  accent,
  dark,
  pinned,
  dashedAdd,
  removable,
}

class MacrovaChip extends StatelessWidget {
  final String label;
  final bool selected;
  final MacrovaChipVariant variant;
  final IconData? leadingIcon;
  final VoidCallback? onTap;
  final VoidCallback? onRemove;

  const MacrovaChip({
    super.key,
    required this.label,
    this.selected = false,
    this.variant = MacrovaChipVariant.default_,
    this.leadingIcon,
    this.onTap,
    this.onRemove,
  });

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;
    final colors = _resolveColors(tokens);

    if (variant == MacrovaChipVariant.dashedAdd) {
      return _DashedChip(
        label: label,
        onTap: onTap,
        tokens: tokens,
      );
    }

    final decoration = BoxDecoration(
      color: colors.background,
      borderRadius: MacrovaRadius.borderPill,
      border: Border.all(color: colors.border),
    );

    final child = Padding(
      padding: const EdgeInsets.symmetric(
        horizontal: MacrovaSpacing.md,
        vertical: MacrovaSpacing.xs + 2,
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (leadingIcon != null) ...[
            Icon(leadingIcon, size: 14, color: colors.foreground),
            const SizedBox(width: MacrovaSpacing.xs),
          ],
          Text(
            label,
            style: MacrovaTypography.bodyMedium(colors.foreground),
          ),
          if (variant == MacrovaChipVariant.removable && onRemove != null) ...[
            const SizedBox(width: MacrovaSpacing.xs),
            GestureDetector(
              onTap: onRemove,
              child: Icon(
                Icons.close,
                size: 14,
                color: colors.foreground.withValues(alpha: 0.6),
              ),
            ),
          ],
        ],
      ),
    );

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: MacrovaRadius.borderPill,
        child: Ink(
          decoration: decoration,
          child: child,
        ),
      ),
    );
  }

  _ChipColors _resolveColors(MacrovaTokens tokens) {
    if (selected) {
      return _ChipColors(
        background: tokens.inkPrimary,
        foreground: MacrovaColors.onDarkFill,
        border: tokens.inkPrimary,
      );
    }

    return switch (variant) {
      MacrovaChipVariant.accent => _ChipColors(
          background: tokens.accentSoft,
          foreground: tokens.accentDeep,
          border: Colors.transparent,
        ),
      MacrovaChipVariant.dark => _ChipColors(
          background: tokens.inkPrimary,
          foreground: MacrovaColors.onDarkFill,
          border: tokens.inkPrimary,
        ),
      MacrovaChipVariant.pinned => _ChipColors(
          background: tokens.pinnedSoft,
          foreground: tokens.pinned,
          border: Colors.transparent,
        ),
      MacrovaChipVariant.removable ||
      MacrovaChipVariant.dashedAdd ||
      MacrovaChipVariant.default_ =>
        _ChipColors(
          background: tokens.surfaceSoft,
          foreground: tokens.inkSecondary,
          border: tokens.lineDefault,
        ),
    };
  }
}

class _ChipColors {
  final Color background;
  final Color foreground;
  final Color border;

  const _ChipColors({
    required this.background,
    required this.foreground,
    required this.border,
  });
}

class _DashedChip extends StatelessWidget {
  final String label;
  final VoidCallback? onTap;
  final MacrovaTokens tokens;

  const _DashedChip({
    required this.label,
    required this.onTap,
    required this.tokens,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: MacrovaRadius.borderPill,
        child: CustomPaint(
          painter: DashedBorderPainter(
            color: tokens.lineStrong,
            borderRadius: MacrovaRadius.pill,
          ),
          child: Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: MacrovaSpacing.md,
              vertical: MacrovaSpacing.xs + 2,
            ),
            child: Text(
              label,
              style: MacrovaTypography.bodyMedium(tokens.inkTertiary),
            ),
          ),
        ),
      ),
    );
  }
}
