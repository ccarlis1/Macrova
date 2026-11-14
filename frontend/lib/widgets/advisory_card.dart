import 'package:flutter/material.dart';

import '../theme/tokens.dart';

enum AdvisoryVariant { warn, info }

class AdvisoryCard extends StatelessWidget {
  final AdvisoryVariant variant;
  final String title;
  final String description;

  const AdvisoryCard({
    super.key,
    required this.variant,
    required this.title,
    required this.description,
  });

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;
    final badgeColors = _badgeColors(tokens);

    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: MacrovaRadius.borderMd,
        side: BorderSide(color: tokens.lineDefault),
      ),
      child: Padding(
        padding: const EdgeInsets.all(MacrovaSpacing.lg),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                color: badgeColors.background,
                shape: BoxShape.circle,
              ),
              alignment: Alignment.center,
              child: Text(
                variant == AdvisoryVariant.warn ? '!' : 'i',
                style: MacrovaTypography.label(badgeColors.foreground),
              ),
            ),
            const SizedBox(width: MacrovaSpacing.md),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: MacrovaTypography.bodyMedium(tokens.inkPrimary)
                        .copyWith(fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    description,
                    style: MacrovaTypography.caption(tokens.inkTertiary),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  _BadgeColors _badgeColors(MacrovaTokens tokens) {
    return switch (variant) {
      AdvisoryVariant.warn => _BadgeColors(
          background: tokens.accentSoft,
          foreground: tokens.accentDeep,
        ),
      AdvisoryVariant.info => _BadgeColors(
          background: tokens.surfaceSoft,
          foreground: tokens.inkSecondary,
        ),
    };
  }
}

class _BadgeColors {
  final Color background;
  final Color foreground;

  const _BadgeColors({
    required this.background,
    required this.foreground,
  });
}
