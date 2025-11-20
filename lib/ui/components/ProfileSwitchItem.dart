import 'package:flutter/material.dart';
import '../../core/colors/AppColors.dart';
import 'AppSvgIcon.dart';

class ProfileSwitchItem extends StatelessWidget {
  final String iconLight;
  final String iconDark;
  final String title;
  final String description;
  final bool value;
  final Function(bool) onChanged;

  const ProfileSwitchItem({
    super.key,
    required this.iconLight,
    required this.iconDark,
    required this.title,
    required this.description,
    required this.value,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: theme.cardColor,
        borderRadius: BorderRadius.circular(18),
        boxShadow: [
          BoxShadow(
            color: AppColors.slider.withOpacity(isDark ? 0.3 : 0.1),
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
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: isDark ? AppColors.textDark : AppColors.text,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  description,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: isDark ? AppColors.textDark : AppColors.text,
                  ),
                ),
              ],
            ),
          ),
          Switch(
            value: value,
            onChanged: onChanged,
            thumbColor: MaterialStateProperty.resolveWith<Color>((states) {
              if (states.contains(MaterialState.selected)) {
                return isDark
                    ? AppColors.titleTextDark
                    : AppColors.primaryColor;
              }
              return isDark
                  ? const Color(0xFF2E3A47)
                  : AppColors.textDark;
            }),
            trackColor: MaterialStateProperty.resolveWith<Color>((states) {
              if (states.contains(MaterialState.selected)) {
                return isDark
                    ? AppColors.titleTextDark.withOpacity(0.4)
                    : AppColors.primaryColor.withOpacity(0.4);
              }
              return isDark
                  ? AppColors.inputFieldBackgroundDark
                  : AppColors.inputFieldBackground;
            }),
            materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
          ),
        ],
      ),
    );
  }
}
