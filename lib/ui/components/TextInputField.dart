import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';

class TextInputField extends StatefulWidget {
  final String title;
  final String hintText;
  final String? svgPrefixIcon;
  final bool isPassword;
  final TextEditingController? controller;
  final ValueChanged<String>? onChanged;
  final String? errorText;

  const TextInputField({
    super.key,
    required this.title,
    required this.hintText,
    this.svgPrefixIcon,
    this.isPassword = false,
    this.controller,
    this.onChanged,
    this.errorText,
  });

  @override
  State<TextInputField> createState() => _TextInputFieldState();
}

class _TextInputFieldState extends State<TextInputField> {
  bool _obscureText = true;

  @override
  void initState() {
    super.initState();
    _obscureText = widget.isPassword;
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          widget.title,
          style: theme.textTheme.bodyMedium,
        ),
        const SizedBox(height: 4),
        TextField(
          controller: widget.controller,
          obscureText: _obscureText,
          onChanged: widget.onChanged,
          decoration: InputDecoration(
            hintText: widget.hintText,
            hintStyle: TextStyle(
              color: theme.hintColor,
            ),
            filled: true,
            fillColor: theme.inputDecorationTheme.fillColor,
            enabledBorder: theme.inputDecorationTheme.enabledBorder,
            focusedBorder: theme.inputDecorationTheme.focusedBorder,
            prefixIcon: widget.svgPrefixIcon != null
                ? Padding(
              padding: const EdgeInsets.all(12.0),
              child: SvgPicture.asset(widget.svgPrefixIcon!, width: 20, height: 20),
            )
                : null,
            suffixIcon: widget.isPassword
                ? IconButton(
              icon: Icon(_obscureText ? Icons.visibility : Icons.visibility_off),
              onPressed: () {
                setState(() {
                  _obscureText = !_obscureText;
                });
              },
            )
                : null,
          ),
        ),
        if (widget.errorText != null)
          Padding(
            padding: const EdgeInsets.only(top: 4, left: 4),
            child: Text(
              widget.errorText!,
              style: const TextStyle(color: Colors.red, fontSize: 12),
            ),
          ),
      ],
    );
  }
}