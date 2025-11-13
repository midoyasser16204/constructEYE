
import '../../entities/UserEntity.dart';

abstract class LoginUseCase {
  Future<UserEntity> execute(String email, String password);
}