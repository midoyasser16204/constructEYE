import '../../entities/UserEntity.dart';

abstract class SignUpUseCase {
  Future<UserEntity> execute({
    required String email,
    required String password,
    required String fullName,
  });
}
