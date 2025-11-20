import 'package:flutter/material.dart';
import 'AppSvgIcon.dart';

class NavigationItem extends StatelessWidget {
  final String iconLight;
  final String iconDark;
  final String title;
  final VoidCallback onTap;
  final bool isLogout;

  const NavigationItem({
    super.key,
    required this.iconLight,
    required this.iconDark,
    required this.title,
    required this.onTap,
    this.isLogout = false,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: theme.cardColor,
          borderRadius: BorderRadius.circular(18),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(
                  theme.brightness == Brightness.dark ? 0.3 : 0.1),
              blurRadius: 12,
              offset: const Offset(0, 6),
            ),
          ],
        ),
        child: Row(
          children: [
            AppSvgIcon(lightPath: iconLight, darkPath: iconDark, size: 40),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                title,
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: isLogout
                      ? Colors.red
                      : theme.textTheme.bodyMedium?.color,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
            Icon(
              Icons.arrow_forward_ios,
              size: 16,
              color: theme.textTheme.bodyMedium?.color,
            ),
          ],
        ),
      ),
    );
  }
}
