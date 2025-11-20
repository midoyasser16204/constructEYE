import 'dart:io';
import 'package:constructEYE/di/DependencyInjection.dart';
import 'package:flutter/material.dart';
import 'package:flutter_svg/svg.dart';
import '../../../../core/colors/AppColors.dart';
import '../../../../core/constants/AppConstants.dart';
import '../../components/CustomButton.dart';
import '../../components/TextInputField.dart';
import 'edit_profile_bloc/EditProfileContract.dart';
import 'edit_profile_bloc/EditProfileBloc.dart';


class EditProfileScreen extends StatefulWidget {
  const EditProfileScreen({super.key});

  @override
  State<EditProfileScreen> createState() => _EditProfileScreenState();
}

class _EditProfileScreenState extends State<EditProfileScreen> {
  late final EditProfileBloc _bloc = getIt<EditProfileBloc>();

  @override
  void initState() {
    super.initState();
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
        child: Column(
          children: [
            // Header
            Container(
              padding: EdgeInsets.all(screenWidth * 0.05),
              width: double.infinity,
              decoration: BoxDecoration(
                color: theme.primaryColor,
                borderRadius: const BorderRadius.vertical(bottom: Radius.circular(25)),
              ),
              child: Column(
                children: [
                  Row(
                    children: [
                      GestureDetector(
                        onTap: () => Navigator.pop(context),
                        child: Container(
                          width: screenWidth * 0.1,
                          height: screenWidth * 0.1,
                          decoration: BoxDecoration(
                            color: Colors.white.withOpacity(0.1),
                            borderRadius: BorderRadius.circular(screenWidth * 0.04),
                          ),
                          alignment: Alignment.center,
                          child: SvgPicture.asset(
                            AppConstants.blueArrowBackIcon,
                            width: screenWidth * 0.1,
                            height: screenWidth * 0.1,
                          ),
                        ),
                      ),
                      SizedBox(width: screenWidth * 0.02),
                      Text(
                        AppConstants.editProfileTitle,
                        style: theme.textTheme.bodyLarge?.copyWith(
                          fontSize: screenWidth * 0.07,
                          fontWeight: FontWeight.bold,
                          color: AppColors.background,
                        ),
                      ),
                    ],
                  ),
                  SizedBox(height: screenHeight * 0.02),
                  StreamBuilder<EditProfileState>(
                    stream: _bloc.state,
                    initialData: _bloc.currentState,
                    builder: (context, snapshot) {
                      final state = snapshot.data!;
                      return GestureDetector(
                        onTap: () => _bloc.eventSink.add(ChangeImageEvent()),
                        child: Stack(
                          alignment: Alignment.bottomRight,
                          children: [
                            Container(
                              width: screenWidth * 0.25,
                              height: screenWidth * 0.25,
                              decoration: BoxDecoration(
                                color: theme.inputDecorationTheme.fillColor,
                                shape: BoxShape.circle,
                              ),
                              child: state.imagePath == null
                                  ? Center(
                                child: Text(
                                  AppConstants.editProfileName,
                                  style: theme.textTheme.bodyLarge?.copyWith(
                                    fontSize: screenWidth * 0.07,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                              )
                                  : ClipOval(
                                child: Image.file(
                                  File(state.imagePath!),
                                  fit: BoxFit.cover,
                                  width: screenWidth * 0.25,
                                  height: screenWidth * 0.25,
                                ),
                              ),
                            ),
                            Container(
                              width: screenWidth * 0.08,
                              height: screenWidth * 0.08,
                              child: Center(
                                child: SvgPicture.asset(
                                  AppConstants.cameraContainerIcon,
                                  width: screenWidth * 0.1,
                                  height: screenWidth * 0.1,
                                ),
                              ),
                            ),
                          ],
                        ),
                      );
                    },
                  ),
                  SizedBox(height: screenHeight * 0.01),
                  Text(
                    AppConstants.changeProfilePicture,
                    style: TextStyle(
                      color: AppColors.background,
                      fontSize: screenWidth * 0.04,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ],
              ),
            ),

            // Body
            Expanded(
              child: SingleChildScrollView(
                padding: EdgeInsets.all(screenWidth * 0.045)
                    .copyWith(bottom: MediaQuery.of(context).viewInsets.bottom + screenHeight * 0.02),
                physics: const BouncingScrollPhysics(),
                child: StreamBuilder<EditProfileState>(
                  stream: _bloc.state,
                  initialData: _bloc.currentState,
                  builder: (context, snapshot) {
                    final state = snapshot.data!;
                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // Input fields container
                        Container(
                          width: double.infinity,
                          padding: EdgeInsets.symmetric(
                            horizontal: screenWidth * 0.045,
                            vertical: screenHeight * 0.025,
                          ),
                          margin: EdgeInsets.only(bottom: screenHeight * 0.025),
                          decoration: BoxDecoration(
                            color: theme.cardColor,
                            borderRadius: BorderRadius.circular(18),
                            boxShadow: [
                              BoxShadow(
                                color: Colors.black.withOpacity(theme.brightness == Brightness.dark ? 0.3 : 0.15),
                                blurRadius: 25,
                                spreadRadius: 1,
                                offset: const Offset(0, 12),
                              ),
                            ],
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              TextInputField(
                                title: AppConstants.name,
                                hintText: AppConstants.namePlaceholder,
                                controller: state.nameController,
                                onChanged: (v) => _bloc.eventSink.add(NameChanged(v)),
                              ),
                              SizedBox(height: screenHeight * 0.02),
                              TextInputField(
                                title: AppConstants.postion,
                                hintText: AppConstants.positionPlaceholder,
                                controller: state.roleController,
                                onChanged: (v) => _bloc.eventSink.add(RoleChanged(v)),
                              ),
                              SizedBox(height: screenHeight * 0.02),
                              TextInputField(
                                title: AppConstants.emailAddress,
                                hintText: AppConstants.emailPlaceholder,
                                controller: state.emailController,
                                onChanged: (v) => _bloc.eventSink.add(EmailChanged(v)),
                              ),
                              SizedBox(height: screenHeight * 0.02),
                              TextInputField(
                                title: AppConstants.phoneNumber,
                                hintText: AppConstants.phonePlaceholder,
                                controller: state.phoneController,
                                onChanged: (v) => _bloc.eventSink.add(PhoneChanged(v)),
                              ),
                              SizedBox(height: screenHeight * 0.02),
                              TextInputField(
                                title: AppConstants.companyName,
                                hintText: AppConstants.companyPlaceholder,
                                controller: state.companyController,
                                onChanged: (v) => _bloc.eventSink.add(CompanyChanged(v)),
                              ),
                            ],
                          ),
                        ),

                        // Save Button
                        CustomButton(
                          text: AppConstants.saveChange,
                          onPressed: () => _bloc.eventSink.add(SaveProfileEvent()),
                        ),
                        SizedBox(height: screenHeight * 0.015),

                        // Cancel Button
                        CustomButton(
                          text: AppConstants.cancelButtonTitle,
                          onPressed: () => Navigator.pop(context),
                        ),
                        SizedBox(height: screenHeight * 0.03),
                      ],
                    );
                  },
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
