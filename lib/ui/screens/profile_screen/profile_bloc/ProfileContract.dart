import 'package:flutter/material.dart';

class ProfileState {
  final String name;
  final String role;
  final String email;
  final String phone;
  final String company;

  final bool pushNotifications;
  final bool safetyAlerts;

  ProfileState({
    required this.name,
    required this.role,
    required this.email,
    required this.phone,
    required this.company,
    this.pushNotifications = true,
    this.safetyAlerts = true,
  });

  ProfileState copyWith({
    String? name,
    String? role,
    String? email,
    String? phone,
    String? company,
    bool? isDarkMode,
    bool? pushNotifications,
    bool? safetyAlerts,
  }) {
    return ProfileState(
      name: name ?? this.name,
      role: role ?? this.role,
      email: email ?? this.email,
      phone: phone ?? this.phone,
      company: company ?? this.company,
      pushNotifications: pushNotifications ?? this.pushNotifications,
      safetyAlerts: safetyAlerts ?? this.safetyAlerts,
    );
  }
}

abstract class ProfileEvent {}

class TogglePushNotifications extends ProfileEvent {
  final bool value;
  TogglePushNotifications(this.value);
}

class ToggleSafetyAlerts extends ProfileEvent {
  final bool value;
  ToggleSafetyAlerts(this.value);
}

class LogoutEvent extends ProfileEvent {}
