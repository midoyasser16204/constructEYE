import 'package:flutter/material.dart';

/// --------------------- STATE ---------------------
class EditProfileState {
  final TextEditingController nameController;
  final TextEditingController roleController;
  final TextEditingController emailController;
  final TextEditingController phoneController;
  final TextEditingController companyController;
  final String? imagePath;

  EditProfileState({
    required this.nameController,
    required this.roleController,
    required this.emailController,
    required this.phoneController,
    required this.companyController,
    this.imagePath,
  });

  EditProfileState copyWith({
    TextEditingController? nameController,
    TextEditingController? roleController,
    TextEditingController? emailController,
    TextEditingController? phoneController,
    TextEditingController? companyController,
    String? imagePath,
  }) {
    return EditProfileState(
      nameController: nameController ?? this.nameController,
      roleController: roleController ?? this.roleController,
      emailController: emailController ?? this.emailController,
      phoneController: phoneController ?? this.phoneController,
      companyController: companyController ?? this.companyController,
      imagePath: imagePath ?? this.imagePath,
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
