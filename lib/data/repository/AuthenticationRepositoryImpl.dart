import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:constructEYE/data/data_source/shared_pref/ISharedPrefDataSource.dart';
import 'package:constructEYE/domain/entities/UserEntity.dart';
import 'package:firebase_auth/firebase_auth.dart';
import '../../domain/repository/AuthenticationRepository.dart';

class AuthenticationRepositoryImpl implements AuthenticationRepository {
  final FirebaseAuth _firebaseAuth;
  final FirebaseFirestore _firestore;
  final SharedPrefDataSource _sharedPref;

  AuthenticationRepositoryImpl({
    required FirebaseAuth firebaseAuth,
    required FirebaseFirestore firestore,
    required SharedPrefDataSource sharedPref,
  }) : _firebaseAuth = firebaseAuth,
       _firestore = firestore,
       _sharedPref = sharedPref;

  @override
  Future<UserEntity> login({
    required String email,
    required String password,
  }) async {
    try {
      final userCredential = await _firebaseAuth.signInWithEmailAndPassword(
        email: email,
        password: password,
      );

      final userDoc = await _firestore
          .collection('users')
          .doc(userCredential.user!.uid)
          .get();
      final userEntity = UserEntity.fromMap(userDoc.data()!);

      // حفظ UID في SharedPreferences
      await _sharedPref.saveUid(uid:userEntity.uid);

      return userEntity;
    } catch (e) {
      throw Exception('Login failed: ${e.toString()}');
    }
  }

  @override
  Future<void> logout() async {
    await _firebaseAuth.signOut();
    await _sharedPref.removeUid();
  }

  @override
  Future<UserEntity> register({
    required String email,
    required String password,
    required String fullName,
  }) async {
    try {
      UserCredential userCredential = await _firebaseAuth
          .createUserWithEmailAndPassword(email: email, password: password);

      final userEntity = UserEntity.dart(
        uid: userCredential.user!.uid,
        email: email,
        fullName: fullName,
      );

      await _firestore
          .collection('users')
          .doc(userEntity.uid)
          .set(userEntity.toMap());

      // حفظ UID في SharedPreferences
      await _sharedPref.saveUid(uid:userEntity.uid);

      return userEntity;
    } catch (e) {
      throw Exception('Registration failed: ${e.toString()}');
    }
  }

  @override
  Future<void> forgotPassword({required String email}) async {
    try {
      await _firebaseAuth.sendPasswordResetEmail(email: email);
    } catch (e) {
      throw Exception('Failed to send reset email: ${e.toString()}');
    }
  }

  @override
  Future<UserEntity?> getCurrentUser() async {
    final user = _firebaseAuth.currentUser;
    if (user == null) return null;

    final userDoc = await _firestore.collection('users').doc(user.uid).get();
    return UserEntity.fromMap(userDoc.data()!);
  }
}
