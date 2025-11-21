import 'dart:io';

import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:constructEYE/domain/entities/UserEntity.dart';
import 'package:firebase_storage/firebase_storage.dart';

import '../../domain/repository/UserRepository.dart';
import '../data_source/shared_pref/SharedPrefDataSource.dart';

class UserRepositoryImpl implements UserRepository {
  final FirebaseFirestore _firestore;
  final FirebaseStorage _storage;
  final SharedPrefDataSource _sharedPref;

  UserRepositoryImpl({
    required FirebaseFirestore firestore,
    required SharedPrefDataSource sharedPref,
    required FirebaseStorage storage,
  }) : _firestore = firestore,
       _sharedPref = sharedPref,
       _storage = storage;

  @override
  Future<UserEntity?> getCurrentUser() async {
    // 1️⃣ Get UID from SharedPreferences
    final uid = _sharedPref.getUid();
    if (uid == null) return null;

    // 2️⃣ Fetch user document from Firestore by UID
    final userDoc = await _firestore.collection('users').doc(uid).get();
    if (!userDoc.exists || userDoc.data() == null) return null;

    final userEntity = UserEntity.fromMap(userDoc.data()!);

    return userEntity;
  }

  @override
  Future<UserEntity> updateUserProfile(UserEntity user, File? newImage) async {
    try {
      String? imageUrl = user.profilePictureUrl;

      if (newImage != null) {
        final storageRef = FirebaseStorage.instance
            .ref()
            .child('profile_pictures/${user.uid}.jpg');

        await storageRef.putFile(newImage);

        imageUrl = await storageRef.getDownloadURL();
      }

      // بيانات التحديث
      final updatedData = {
        'fullName': user.fullName,
        'phone': user.phone,
        'role': user.role,
        'company': user.company,
        'profilePictureUrl': imageUrl,
      };

      // تحديث Firestore
      await _firestore.collection('users').doc(user.uid).update(updatedData);

      // رجّع النسخة الجديدة
      return UserEntity(
        uid: user.uid,
        email: user.email,
        fullName: user.fullName,
        profilePictureUrl: imageUrl,
        phone: user.phone,
        role: user.role,
        company: user.company,
      );
    } catch (e) {
      throw Exception("Update failed: ${e.toString()}");
    }
  }
}