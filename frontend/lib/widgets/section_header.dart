import 'package:flutter/material.dart';

import '../theme/tokens.dart';

class SectionHeader extends StatelessWidget {
  final String title;
  final String? subtitle;
  final String? linkLabel;
  final VoidCallback? onLink;
  final Widget? action;

  const SectionHeader({
    super.key,
    required this.title,
    this.subtitle,
    this.linkLabel,
    this.onLink,
    this.action,
  });

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;

    return Padding(
      padding: const EdgeInsets.only(bottom: MacrovaSpacing.md),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: Theme.of(context).textTheme.titleLarge,
                  overflow: TextOverflow.ellipsis,
                ),
                if (subtitle != null) ...[
                  const SizedBox(height: MacrovaSpacing.xs),
                  Text(
                    subtitle!,
                    style: MacrovaTypography.bodyMedium(tokens.inkTertiary),
                  ),
                ],
              ],
            ),
          ),
          if (linkLabel != null && onLink != null) ...[
            const SizedBox(width: MacrovaSpacing.sm),
            TextButton(
              onPressed: onLink,
              style: TextButton.styleFrom(
                padding: EdgeInsets.zero,
                minimumSize: Size.zero,
                tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                foregroundColor: tokens.accent,
              ),
              child: Text(
                linkLabel!,
                style: MacrovaTypography.label(tokens.accent).copyWith(
                  decoration: TextDecoration.underline,
                  decorationColor: tokens.accent,
                ),
              ),
            ),
          ],
          if (action != null) ...[
            const SizedBox(width: MacrovaSpacing.sm),
            action!,
          ],
        ],
      ),
    );
  }
}
