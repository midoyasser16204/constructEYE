import 'dart:ui';

class UserEntity {
  final String uid;
  final String email;
  final String fullName;
  final String? profilePictureUrl;
  final String phone;
  final String role;
  final String company;

  UserEntity({
    required this.uid,
    required this.email,
    required this.fullName,
    this.profilePictureUrl,
    required this.phone,
    required this.role,
    required this.company,
  });

  factory UserEntity.fromMap(Map<String, dynamic> map) {
    return UserEntity(
      uid: map['uid'],
      email: map['email'],
      fullName: map['fullName'],
      profilePictureUrl: map['profilePictureUrl'],
      phone: map['phone'],
      role: map['role'],
      company: map['company'],
    );
  }

  Map<String, dynamic> toMap() {
    return {
      'uid': uid,
      'email': email,
      'fullName': fullName,
      'profilePictureUrl': profilePictureUrl,
      'phone': phone,
      'role': role,
      'company': company,
    };
  }
}
