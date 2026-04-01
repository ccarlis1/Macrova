import 'package:flutter/material.dart';

class OptimizeCartButton extends StatelessWidget {
  const OptimizeCartButton({
    super.key,
    required this.onPressed,
    required this.busy,
  });

  final VoidCallback? onPressed;
  final bool busy;

  @override
  Widget build(BuildContext context) {
    return FilledButton.tonalIcon(
      onPressed: busy ? null : onPressed,
      icon: busy
          ? const SizedBox(
              width: 18,
              height: 18,
              child: CircularProgressIndicator(strokeWidth: 2),
            )
          : const Icon(Icons.shopping_cart_outlined),
      label: Text(busy ? 'Starting…' : 'Optimize Grocery Cart'),
    );
  }
}
