import 'package:constructEYE/core/themes/AppThemes.dart';
import 'package:constructEYE/di/DependencyInjection.dart';
import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:provider/provider.dart';
import '../../../core/constants/AppConstants.dart';
import '../../../core/colors/AppColors.dart';
import '../../components/SectionTitle.dart';
import '../../components/ProfileCardItem.dart';
import '../../components/ProfileSwitchItem.dart';
import '../../components/NavigationItem.dart';
import '../edit_profile_screen/EditProfileScreen.dart';
import 'profile_bloc/ProfileBloc.dart';
import 'profile_bloc/ProfileContract.dart';
import '../../../main.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  late final ProfileBloc _bloc = getIt<ProfileBloc>();

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

    final themeProvider = Provider.of<ThemeProvider>(context);

    return Scaffold(
      backgroundColor: theme.scaffoldBackgroundColor,
      body: SafeArea(
        child: StreamBuilder<ProfileState>(
          stream: _bloc.state,
          initialData: _bloc.currentState,
          builder: (context, snapshot) {
            final state = snapshot.data!;

            if (state.isLoggedOut) {
              Future.microtask(() {
                Navigator.pushReplacementNamed(
                  context,
                  AppConstants.loginScreenRoute,
                );
              });
            }

            return Column(
              children: [
                // ------------------ HEADER ------------------
                Container(
                  width: double.infinity,
                  padding: EdgeInsets.symmetric(
                    horizontal: screenWidth * 0.03,
                    vertical: screenHeight * 0.03,
                  ),
                  decoration: BoxDecoration(
                    color: AppColors.primaryColor,
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
                      SizedBox(height: screenHeight * 0.02),
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
                            state.imageUrl != null &&
                                state.imageUrl!.isNotEmpty
                                ? ClipOval(
                              child: Image.network(
                                state.imageUrl!,
                                fit: BoxFit.cover,
                                width: screenWidth * 0.2,
                                height: screenWidth * 0.2,
                              ),
                            )
                                : SvgPicture.asset(
                              AppConstants.personIcon,
                              width: screenWidth * 0.15,
                              height: screenWidth * 0.15,
                              color: AppColors.primaryColor,
                            ),
                            SizedBox(width: screenWidth * 0.04),
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
                                    color: AppColors.primaryColor,
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
                        SectionTitle(
                          text: AppConstants.accountInformationTitle,
                        ),
                        ProfileCardItem(
                          iconLight: AppConstants.mailContainerIcon,
                          iconDark: AppConstants.mailContainerDarkIcon,
                          title: AppConstants.email,
                          value: state.email,
                        ),
                        ProfileCardItem(
                          iconLight: AppConstants.phoneContainerIcon,
                          iconDark: AppConstants.phoneContainerDarkIcon,
                          title: AppConstants.phoneNumber,
                          value: state.phone,
                        ),
                        ProfileCardItem(
                          iconLight: AppConstants.companyContainerIcon,
                          iconDark: AppConstants.companyContainerDarkIcon,
                          title: AppConstants.companyName,
                          value: state.company,
                        ),

                        SizedBox(height: screenHeight * 0.02),
                        SectionTitle(text: AppConstants.preferencesTitle),

                        // ---------------- DARK MODE SWITCH ----------------
                        ProfileSwitchItem(
                          iconLight: AppConstants.themeContainerIcon,
                          iconDark: AppConstants.themeContainerDarkIcon,
                          title: AppConstants.darkModeTitle,
                          description: AppConstants.darkModeDescription,
                          value: themeProvider.isDark,
                          onChanged: (v) => themeProvider.toggleTheme(),
                        ),

                        ProfileSwitchItem(
                          iconLight: AppConstants.notificationContainerIcon,
                          iconDark: AppConstants.notificationContainerDarkIcon,
                          title: AppConstants.pushNotificationsTitle,
                          description:
                              AppConstants.pushNotificationsDescription,
                          value: state.pushNotifications,
                          onChanged: (v) =>
                              _bloc.eventSink.add(TogglePushNotifications(v)),
                        ),

                        ProfileSwitchItem(
                          iconLight: AppConstants.safetyContainerIcon,
                          iconDark: AppConstants.safetyContainerDarkIcon,
                          title: AppConstants.safetyAlertsTitle,
                          description: AppConstants.safetyAlertsDescription,
                          value: state.safetyAlerts,
                          onChanged: (v) =>
                              _bloc.eventSink.add(ToggleSafetyAlerts(v)),
                        ),

                        SizedBox(height: screenHeight * 0.02),
                        SectionTitle(text: AppConstants.otherTitle),
                        NavigationItem(
                          iconLight: AppConstants.passwordContainerIcon,
                          iconDark: AppConstants.passwordContainerDarkIcon,
                          title: AppConstants.changePasswordTitle,
                          onTap: () {},
                        ),
                        NavigationItem(
                          iconLight: AppConstants.mailContainerIcon,
                          iconDark: AppConstants.mailContainerDarkIcon,
                          title: AppConstants.helpSupportTitle,
                          onTap: () {},
                        ),
                        NavigationItem(
                          iconLight: AppConstants.logoutContainerIcon,
                          iconDark: AppConstants.logoutContainerDarkIcon,
                          title: AppConstants.logoutTitle,
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
}
