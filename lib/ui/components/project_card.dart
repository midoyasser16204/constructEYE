import 'package:constructEYE/core/constants/AppConstants.dart';
import 'package:flutter/material.dart';
import 'package:flutter_svg/svg.dart';

class ProjectCard extends StatelessWidget {
  final String title;
  final String location;
  final int progress;
  final String status;
  final String imagePath;

  const ProjectCard({
    super.key,
    required this.title,
    required this.location,
    required this.progress,
    required this.status,
    required this.imagePath,
  });

  // Dynamic status colors based on theme brightness
  Color getStatusColor(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    switch (status.toLowerCase()) {
      case "on track":
        return isDark ? Colors.green.shade400 : Colors.green.shade600;
      case "active":
        return isDark ? Colors.orange.shade400 : Colors.orange.shade600;
      case "final phase":
        return isDark ? Colors.blue.shade400 : Colors.blue.shade600;
      case "in progress":
        return isDark ? Colors.amber.shade400 : Colors.amber.shade700;
      default:
        return isDark ? Colors.grey.shade400 : Colors.grey.shade600;
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Container(
      margin: const EdgeInsets.symmetric(vertical: 10, horizontal: 16),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: theme.cardColor,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.08),
            blurRadius: 6,
            offset: const Offset(0, 3),
          )
        ],
      ),
      child: Row(
        children: [
          // ----------- Image ---------------
          ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: Image.asset(
              imagePath,
              height: 75,
              width: 75,
              fit: BoxFit.cover,
            ),
          ),

          const SizedBox(width: 16),

          // ----------- Project Info ---------------
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                /// Title
                Text(
                  title,
                  style: theme.textTheme.bodyLarge?.copyWith(
                    fontSize: 17,
                    fontWeight: FontWeight.bold,
                  ),
                ),

                const SizedBox(height: 4),

                /// Location
                Row(
                  children: [
                    SvgPicture.asset(
                      AppConstants.locationIcon,
                      height: 16,
                      width: 16,
                      color: theme.iconTheme.color,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      location,
                      style: theme.textTheme.bodyMedium?.copyWith(
                        fontSize: 13,
                        color: theme.textTheme.bodyMedium?.color?.withOpacity(0.6),
                      ),
                    ),
                  ],
                ),

                const SizedBox(height: 12),

                /// Progress & Bar
                Row(
                  children: [
                    Text(
                      "Progress",
                      style: theme.textTheme.bodyMedium?.copyWith(
                        fontSize: 13,
                      ),
                    ),
                    const Spacer(),
                    Text(
                      "$progress%",
                      style: theme.textTheme.bodyMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),

                const SizedBox(height: 4),

                /// Progress Bar
                ClipRRect(
                  borderRadius: BorderRadius.circular(10),
                  child: LinearProgressIndicator(
                    value: progress / 100,
                    minHeight: 6,
                    backgroundColor: theme.dividerColor.withOpacity(0.3),
                    valueColor: AlwaysStoppedAnimation<Color>(
                      theme.colorScheme.secondary,
                    ),
                  ),
                ),

                const SizedBox(height: 10),

                /// Status Chip
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                  decoration: BoxDecoration(
                    color: getStatusColor(context),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    status,
                    style: theme.textTheme.bodyMedium?.copyWith(
                      fontSize: 12,
                      color: Colors.white,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                )
              ],
            ),
          )
        ],
      ),
    );
  }
}
