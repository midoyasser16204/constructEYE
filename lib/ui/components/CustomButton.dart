import 'package:flutter/material.dart';
import '../../core/colors/AppColors.dart';

class CustomButton extends StatelessWidget {
  final String text;
  final VoidCallback? onPressed;

  const CustomButton({
    super.key,
    required this.text,
    this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return GestureDetector(
      onTap: onPressed,
      child: Container(
        width: double.infinity,
        height: 50,
        decoration: BoxDecoration(
          color: theme.colorScheme.primary, // from Theme
          borderRadius: BorderRadius.circular(15),
        ),
        alignment: Alignment.center,
        child: Text(
          text,
          style: TextStyle(
            color: AppColors.secondaryColor,
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
    );
  }
}
