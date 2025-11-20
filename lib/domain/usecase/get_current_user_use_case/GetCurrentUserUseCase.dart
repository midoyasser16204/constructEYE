import 'package:constructEYE/domain/entities/UserEntity.dart';

abstract class GetCurrentUserUseCase {
  Future<UserEntity?> execute();
}