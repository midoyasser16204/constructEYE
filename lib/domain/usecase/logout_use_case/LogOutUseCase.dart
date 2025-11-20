import '../../repository/AuthenticationRepository.dart';

abstract class LogoutUseCase {
  Future<void> call();
}
