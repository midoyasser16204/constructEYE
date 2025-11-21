import 'package:flutter/material.dart';

import '../../../../domain/entities/UserEntity.dart';

/// --------------------- STATE ---------------------
class EditProfileState {
  final TextEditingController nameController;
  final TextEditingController roleController;
  final TextEditingController emailController;
  final TextEditingController phoneController;
  final TextEditingController companyController;

  final String? imagePath;
  final String? imageUrl;

  final bool isLoading;
  final bool isSuccess;
  final String? errorMessage;

  final UserEntity? userEntity;

  EditProfileState({
    required this.nameController,
    required this.roleController,
    required this.emailController,
    required this.phoneController,
    required this.companyController,
    this.imagePath,
    this.imageUrl,
    this.userEntity,
    this.errorMessage,
    this.isSuccess = false,
    this.isLoading = false,
  });

  EditProfileState copyWith({
    TextEditingController? nameController,
    TextEditingController? roleController,
    TextEditingController? emailController,
    TextEditingController? phoneController,
    TextEditingController? companyController,
    String? imagePath,
    String? imageUrl,

    bool? isLoading,
    bool? isSuccess,
    String? errorMessage,
    UserEntity? userEntity,
  }) {
    return EditProfileState(
      nameController: nameController ?? this.nameController,
      roleController: roleController ?? this.roleController,
      emailController: emailController ?? this.emailController,
      phoneController: phoneController ?? this.phoneController,
      companyController: companyController ?? this.companyController,
      imagePath: imagePath ?? this.imagePath,
      imageUrl: imageUrl ?? this.imageUrl,
      isLoading: isLoading ?? this.isLoading,
      isSuccess: isSuccess ?? this.isSuccess,
      errorMessage: errorMessage,
      userEntity: userEntity ?? this.userEntity,
    );
  }
}


/// --------------------- EVENTS ---------------------
abstract class EditProfileEvent {}

class ChangeImageEvent extends EditProfileEvent {}
class SaveProfileEvent extends EditProfileEvent {}

class NameChanged extends EditProfileEvent {
  final String name;
  NameChanged(this.name);
}

class RoleChanged extends EditProfileEvent {
  final String role;
  RoleChanged(this.role);
}

class EmailChanged extends EditProfileEvent {
  final String email;
  EmailChanged(this.email);
}

class PhoneChanged extends EditProfileEvent {
  final String phone;
  PhoneChanged(this.phone);
}

class CompanyChanged extends EditProfileEvent {
  final String company;
  CompanyChanged(this.company);
}
