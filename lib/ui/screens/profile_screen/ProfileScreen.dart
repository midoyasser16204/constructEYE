import 'package:flutter/material.dart';
import 'package:flutter_svg/svg.dart';
import '../../../core/constants/AppConstants.dart';
import '../../../core/colors/AppColors.dart';
import '../edit_profile_screen/EditProfileScreen.dart';
import 'profile_bloc/ProfileBloc.dart';
import 'profile_bloc/ProfileContract.dart';
import '../../../core/themes/ThemeNotifier.dart';

class ProfileScreen extends StatefulWidget {
  final ThemeNotifier themeNotifier;
  const ProfileScreen({super.key, required this.themeNotifier});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  late final ProfileBloc _bloc;

  @override
  void initState() {
    super.initState();
    _bloc = ProfileBloc();
  }

  @override
  void dispose() {
    _bloc.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final screenHeight = MediaQuery.of(context).size.height;
    final screenWidth = MediaQuery.of(context).size.width;

    return Scaffold(
      backgroundColor: theme.scaffoldBackgroundColor,
      body: SafeArea(
        child: StreamBuilder<ProfileState>(
          stream: _bloc.state,
          initialData: _bloc.currentState,
          builder: (context, snapshot) {
            final state = snapshot.data!;
            return Column(
              children: [
                // ------------------ HEADER ------------------
                Container(
                  width: double.infinity,
                  padding: EdgeInsets.symmetric(
                    horizontal: screenWidth * 0.05,
                    vertical: screenHeight * 0.05,
                  ),
                  decoration: BoxDecoration(
                    color: theme.primaryColor,
                    borderRadius: const BorderRadius.vertical(
                      bottom: Radius.circular(30),
                    ),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        "Profile",
                        style: theme.textTheme.bodyLarge?.copyWith(
                          fontSize: screenWidth * 0.06,
                          fontWeight: FontWeight.bold,
                          color: AppColors.background,
                        ),
                      ),
                      SizedBox(
                        height: screenHeight * 0.02,
                      ),
                      Container(
                        padding: EdgeInsets.all(screenWidth * 0.06),
                        decoration: BoxDecoration(
                          color: theme.scaffoldBackgroundColor,
                          borderRadius: BorderRadius.circular(20),
                          boxShadow: [
                            BoxShadow(
                              color: Colors.black.withOpacity(0.1),
                              blurRadius: 12,
                              offset: const Offset(0, 6),
                            ),
                          ],
                        ),
                        child: Row(
                          children: [
                            // Avatar
                            Container(
                              width: screenWidth * 0.2,
                              height: screenWidth * 0.2,
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                color: theme.primaryColor,
                              ),
                              alignment: Alignment.center,
                              child: Text(
                                state.name.substring(0, 2).toUpperCase(),
                                style: theme.textTheme.bodyLarge?.copyWith(
                                  color: AppColors.background,
                                  fontSize: screenWidth * 0.07,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ),
                            SizedBox(width: screenWidth * 0.04),
                            // Name + Role
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    state.name,
                                    style: theme.textTheme.bodyLarge?.copyWith(
                                      fontSize: screenWidth * 0.055,
                                      fontWeight: FontWeight.bold,
                                      color: theme.textTheme.bodyLarge?.color,
                                    ),
                                  ),
                                  Text(
                                    state.role,
                                    style: theme.textTheme.bodyMedium?.copyWith(
                                      fontSize: screenWidth * 0.037,
                                      color: theme.textTheme.bodyMedium?.color,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            // Edit Button
                            GestureDetector(
                              onTap: () {
                                Navigator.push(
                                  context,
                                  MaterialPageRoute(
                                    builder: (_) => const EditProfileScreen(),
                                  ),
                                );
                              },
                              child: Container(
                                padding: EdgeInsets.symmetric(
                                  horizontal: screenWidth * 0.04,
                                  vertical: 8,
                                ),
                                child: Text(
                                  AppConstants.editButton,
                                  style: TextStyle(
                                    color: theme.primaryColor,
                                    fontWeight: FontWeight.bold,
                                    fontSize: screenWidth * 0.04,
                                  ),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
                // ------------------ BODY ------------------
                Expanded(
                  child: SingleChildScrollView(
                    padding: EdgeInsets.symmetric(
                      horizontal: screenWidth * 0.045,
                      vertical: screenHeight * 0.02,
                    ),
                    physics: const BouncingScrollPhysics(),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        sectionTitle("ACCOUNT INFORMATION", theme),
                        profileItem(
                          icon: AppConstants.mailContainerIcon,
                          title: "Email",
                          value: state.email,
                          theme: theme,
                        ),
                        profileItem(
                          icon: AppConstants.phoneContainerIcon,
                          title: "Phone",
                          value: state.phone,
                          theme: theme,
                        ),
                        profileItem(
                          icon: AppConstants.companyContainerIcon,
                          title: "Company",
                          value: state.company,
                          theme: theme,
                        ),
                        SizedBox(height: screenHeight * 0.02),
                        sectionTitle("PREFERENCES", theme),
                        switchItem(
                          icon: AppConstants.themeContainerIcon,
                          title: "Dark Mode",
                          value: state.isDarkMode,
                          onChanged: (v) {
                            _bloc.eventSink.add(ToggleDarkMode(v));
                            widget.themeNotifier.toggleTheme(v); // فعلنا الثيم
                          },
                          theme: theme,
                        ),
                        switchItem(
                          icon: AppConstants.notificationContainerIcon,
                          title: "Push Notifications",
                          value: state.pushNotifications,
                          onChanged: (v) =>
                              _bloc.eventSink.add(TogglePushNotifications(v)),
                          theme: theme,
                        ),
                        switchItem(
                          icon: AppConstants.safetyContainerIcon,
                          title: "Safety Alerts",
                          value: state.safetyAlerts,
                          onChanged: (v) =>
                              _bloc.eventSink.add(ToggleSafetyAlerts(v)),
                          theme: theme,
                        ),
                        SizedBox(height: screenHeight * 0.02),
                        sectionTitle("OTHER", theme),
                        navigationItem(
                          icon: AppConstants.passwordContainerIcon,
                          title: "Change Password",
                          theme: theme,
                          onTap: () {},
                        ),
                        navigationItem(
                          icon: AppConstants.mailContainerIcon,
                          title: "Help & Support",
                          theme: theme,
                          onTap: () {},
                        ),
                        navigationItem(
                          icon: AppConstants.logoutContainerIcon,
                          title: "Logout",
                          theme: theme,
                          onTap: () => _bloc.eventSink.add(LogoutEvent()),
                          isLogout: true,
                        ),
                        SizedBox(height: screenHeight * 0.03),
                      ],
                    ),
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }

  // ---------------- UI COMPONENTS ------------------
  Widget sectionTitle(String text, ThemeData theme) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Text(
        text,
        style: theme.textTheme.bodyMedium?.copyWith(
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }

  Widget profileItem({
    required String icon,
    required String title,
    required String value,
    required ThemeData theme,
  }) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: theme.cardColor,
        borderRadius: BorderRadius.circular(18),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(
              theme.brightness == Brightness.dark ? 0.3 : 0.1,
            ),
            blurRadius: 12,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: Row(
        children: [
          SvgPicture.asset(icon, width: 26),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
                ),
                Text(value, style: theme.textTheme.bodyMedium),
              ],
            ),
          ),
          Icon(
            Icons.arrow_forward_ios,
            size: 16,
            color: theme.textTheme.bodyMedium?.color,
          ),
        ],
      ),
    );
  }

  Widget switchItem({
    required String icon,
    required String title,
    required bool value,
    required Function(bool) onChanged,
    required ThemeData theme,
  }) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: theme.cardColor,
        borderRadius: BorderRadius.circular(18),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(
              theme.brightness == Brightness.dark ? 0.3 : 0.1,
            ),
            blurRadius: 12,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: Row(
        children: [
          SvgPicture.asset(icon, width: 26),
          const SizedBox(width: 12),
          Expanded(child: Text(title, style: theme.textTheme.bodyMedium)),
          Switch(
            value: value,
            onChanged: onChanged,
            activeColor: theme.textTheme.bodyMedium?.color,
            inactiveThumbColor: Colors.grey[300],
            inactiveTrackColor: Colors.grey[200],
            materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
          ),
        ],
      ),
    );
  }

  Widget navigationItem({
    required String icon,
    required String title,
    required ThemeData theme,
    required VoidCallback onTap,
    bool isLogout = false,
  }) {
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
                theme.brightness == Brightness.dark ? 0.3 : 0.1,
              ),
              blurRadius: 12,
              offset: const Offset(0, 6),
            ),
          ],
        ),
        child: Row(
          children: [
            SvgPicture.asset(icon, width: 26),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                title,
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: isLogout
                      ? AppColors.errorColor
                      : theme.textTheme.bodyMedium?.color,
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
