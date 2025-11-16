import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';

class AppSvgIcon extends StatelessWidget {
  final String lightPath;
  final String darkPath;
  final double size;

  const AppSvgIcon({
    super.key,
    required this.lightPath,
    required this.darkPath,
    this.size = 24,
  });

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return SvgPicture.asset(
      isDark ? darkPath : lightPath,
      width: size,
      height: size,
    );
  }
}