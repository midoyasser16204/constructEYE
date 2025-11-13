class UserEntity {
  final String uid;
  final String email;
  final String fullName;

  UserEntity.dart({
    required this.uid,
    required this.email,
    required this.fullName,
  });

  factory UserEntity.fromMap(Map<String, dynamic> map) {
    return UserEntity.dart(
      uid: map['uid'],
      email: map['email'],
      fullName: map['fullName'],
    );
  }

  Map<String, dynamic> toMap() {
    return {
      'uid': uid,
      'email': email,
      'fullName': fullName,
    };
  }
}
